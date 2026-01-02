import os
import re
import time
import aiohttp
import asyncio
import logging
import aiofiles
from typing import Optional, Tuple, Dict, Any
from urllib.parse import unquote, urlparse, parse_qs
from config import Config
from utils.progress import Progress
from utils.helpers import sanitize_filename, extract_gdrive_id, extract_terabox_id

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self):
        self.progress = Progress()
        self.chunk_size = Config.CHUNK_SIZE
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=3600)
            connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_gdrive_info(self, file_id: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Get Google Drive file info and download URL"""
        try:
            session = await self.get_session()
            
            # Try direct download first
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            async with session.get(download_url, allow_redirects=False) as resp:
                # Check if direct download available
                if resp.status == 302:
                    redirect_url = resp.headers.get('Location', '')
                    
                    # Get filename from content-disposition
                    filename = "gdrive_file"
                    cd = resp.headers.get('Content-Disposition', '')
                    if 'filename=' in cd:
                        match = re.findall('filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', cd)
                        if match:
                            filename = unquote(match[0])
                    
                    return redirect_url, sanitize_filename(filename), None
                
                # For larger files, need to get confirm token
                if resp.status == 200:
                    text = await resp.text()
                    
                    # Check for virus scan warning page
                    confirm_match = re.search(r'confirm=([0-9A-Za-z_-]+)', text)
                    uuid_match = re.search(r'uuid=([0-9A-Za-z_-]+)', text)
                    
                    if confirm_match:
                        confirm_token = confirm_match.group(1)
                        if uuid_match:
                            uuid_token = uuid_match.group(1)
                            download_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={confirm_token}&uuid={uuid_token}"
                        else:
                            download_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={confirm_token}"
                    
                    # Try to extract filename from page
                    filename_match = re.search(r'<span class="uc-name-size"><a[^>]*>([^<]+)</a>', text)
                    if not filename_match:
                        filename_match = re.search(r'"title":"([^"]+)"', text)
                    
                    filename = filename_match.group(1) if filename_match else "gdrive_file"
                    
                    return download_url, sanitize_filename(filename), None
            
            # Alternative method using different endpoint
            api_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
            return api_url, "gdrive_file", None
            
        except Exception as e:
            logger.error(f"GDrive info error: {e}")
            return None, None, None
    
    async def get_terabox_info(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Get Terabox download info"""
        try:
            session = await self.get_session()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.terabox.com/',
            }
            
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    return url, "terabox_file", None
                
                text = await resp.text()
                
                # Extract download link patterns
                download_patterns = [
                    r'"dlink":"([^"]+)"',
                    r'"downloadLink":"([^"]+)"',
                    r'href="(https://[^"]*(?:terabox|1024tera)[^"]*(?:download|file)[^"]*)"',
                    r'"link":"([^"]+)"',
                ]
                
                download_url = None
                for pattern in download_patterns:
                    match = re.search(pattern, text)
                    if match:
                        download_url = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
                        break
                
                # Extract filename
                filename_patterns = [
                    r'"server_filename":"([^"]+)"',
                    r'"filename":"([^"]+)"',
                    r'"name":"([^"]+)"',
                    r'<title>([^<]+?)(?:\s*[-|]|</title>)',
                ]
                
                filename = "terabox_file"
                for pattern in filename_patterns:
                    match = re.search(pattern, text)
                    if match:
                        filename = match.group(1).strip()
                        if filename and filename != "TeraBox":
                            break
                
                # Extract size
                size = None
                size_match = re.search(r'"size":(\d+)', text)
                if size_match:
                    size = int(size_match.group(1))
                
                if download_url:
                    return download_url, sanitize_filename(filename), size
                
                return url, sanitize_filename(filename), size
                
        except Exception as e:
            logger.error(f"Terabox info error: {e}")
            return url, "terabox_file", None
    
    async def download_file(
        self,
        url: str,
        download_path: str,
        progress_message,
        filename: str = "downloading",
        headers: dict = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download file with progress updates"""
        try:
            session = await self.get_session()
            
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
            }
            
            if headers:
                request_headers.update(headers)
            
            async with session.get(url, headers=request_headers, allow_redirects=True) as resp:
                if resp.status not in [200, 206]:
                    return False, None, f"HTTP Error: {resp.status}"
                
                # Get file info from headers
                total_size = int(resp.headers.get('Content-Length', 0))
                
                # Get filename from headers if available
                cd = resp.headers.get('Content-Disposition', '')
                if 'filename=' in cd:
                    matches = re.findall(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', cd)
                    if matches:
                        filename = sanitize_filename(unquote(matches[0]))
                
                # Also check for filename in URL
                if filename == "downloading":
                    url_path = urlparse(str(resp.url)).path
                    if url_path:
                        url_filename = url_path.split('/')[-1]
                        if url_filename and '.' in url_filename:
                            filename = sanitize_filename(unquote(url_filename))
                
                # Full file path
                file_path = os.path.join(download_path, filename)
                
                # Ensure unique filename
                base, ext = os.path.splitext(file_path)
                counter = 1
                while os.path.exists(file_path):
                    file_path = f"{base}_{counter}{ext}"
                    counter += 1
                
                # Download with progress
                downloaded = 0
                start_time = time.time()
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_size):
                        if chunk:
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress
                            if self.progress.should_update() and progress_message:
                                try:
                                    elapsed = time.time() - start_time
                                    speed = downloaded / elapsed if elapsed > 0 else 0
                                    
                                    if total_size > 0:
                                        eta = int((total_size - downloaded) / speed) if speed > 0 else 0
                                    else:
                                        eta = 0
                                        total_size = downloaded
                                    
                                    text = self.progress.get_download_progress_text(
                                        filename, downloaded, total_size if total_size > 0 else downloaded, speed, eta
                                    )
                                    await progress_message.edit_text(text)
                                except Exception as e:
                                    logger.debug(f"Progress update error: {e}")
                
                # Verify file was downloaded
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return True, file_path, None
                else:
                    return False, None, "Download failed - empty file"
        
        except asyncio.CancelledError:
            return False, None, "Download cancelled"
        except asyncio.TimeoutError:
            return False, None, "Download timeout"
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, None, str(e)
    
    async def download_gdrive(
        self,
        url: str,
        download_path: str,
        progress_message
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Google Drive"""
        try:
            file_id = extract_gdrive_id(url)
            if not file_id:
                return False, None, "Invalid Google Drive URL"
            
            download_url, filename, size = await self.get_gdrive_info(file_id)
            
            if not download_url:
                return False, None, "Could not get download URL"
            
            # Add cookies for large files
            headers = {
                'Cookie': 'download_warning_token=1',
            }
            
            return await self.download_file(
                download_url,
                download_path,
                progress_message,
                filename or "gdrive_file",
                headers
            )
        
        except Exception as e:
            logger.error(f"GDrive download error: {e}")
            return False, None, str(e)
    
    async def download_terabox(
        self,
        url: str,
        download_path: str,
        progress_message
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Terabox"""
        try:
            download_url, filename, size = await self.get_terabox_info(url)
            
            if not download_url:
                return False, None, "Could not get download URL"
            
            headers = {
                'Referer': 'https://www.terabox.com/',
            }
            
            return await self.download_file(
                download_url,
                download_path,
                progress_message,
                filename or "terabox_file",
                headers
            )
        
        except Exception as e:
            logger.error(f"Terabox download error: {e}")
            return False, None, str(e)
    
    async def download_direct(
        self,
        url: str,
        download_path: str,
        progress_message
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from direct link"""
        try:
            # Extract filename from URL
            parsed = urlparse(url)
            filename = parsed.path.split('/')[-1]
            
            if filename:
                filename = unquote(filename)
            else:
                filename = "downloaded_file"
            
            return await self.download_file(
                url,
                download_path,
                progress_message,
                sanitize_filename(filename)
            )
        
        except Exception as e:
            logger.error(f"Direct download error: {e}")
            return False, None, str(e)
