import os
import re
import time
import aiohttp
import asyncio
import logging
import aiofiles
from typing import Optional, Tuple, Dict, Any
from urllib.parse import unquote
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
            timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_gdrive_download_url(self, file_id: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Get Google Drive direct download URL and file info"""
        try:
            # First, try to get file info
            info_url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            session = await self.get_session()
            
            async with session.get(info_url, allow_redirects=False) as resp:
                if resp.status == 302:
                    # Direct download available
                    download_url = resp.headers.get('Location')
                    filename = "downloaded_file"
                    
                    # Try to get filename from content-disposition
                    cd = resp.headers.get('Content-Disposition', '')
                    if 'filename=' in cd:
                        filename = re.findall('filename="?([^";\n]+)"?', cd)
                        if filename:
                            filename = unquote(filename[0])
                    
                    return download_url, filename, None
            
            # For large files, we need to confirm
            async with session.get(info_url) as resp:
                text = await resp.text()
                
                # Check for virus scan warning
                if 'confirm=' in text:
                    confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', text)
                    if confirm_match:
                        confirm_code = confirm_match.group(1)
                        download_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={confirm_code}"
                        
                        # Try to get filename
                        filename_match = re.search(r'<a[^>]*>([^<]+)</a>\s*\([^)]+\)', text)
                        filename = filename_match.group(1) if filename_match else "downloaded_file"
                        
                        return download_url, sanitize_filename(filename), None
                
                # Extract filename from page
                filename_match = re.search(r'<title>([^<]+) - Google Drive</title>', text)
                filename = filename_match.group(1) if filename_match else "downloaded_file"
                
                return info_url, sanitize_filename(filename), None
        
        except Exception as e:
            logger.error(f"GDrive URL error: {e}")
            return None, None, None
    
    async def get_terabox_download_info(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Get Terabox download URL and file info"""
        try:
            session = await self.get_session()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()
                
                # Try to extract direct download link
                # This is a simplified version - real Terabox requires more complex handling
                
                # Look for download URL in page
                download_patterns = [
                    r'"dlink":"([^"]+)"',
                    r'"downloadLink":"([^"]+)"',
                    r'href="(https://[^"]*terabox[^"]*download[^"]*)"',
                ]
                
                download_url = None
                for pattern in download_patterns:
                    match = re.search(pattern, text)
                    if match:
                        download_url = match.group(1).replace('\\/', '/')
                        break
                
                # Extract filename
                filename_patterns = [
                    r'"server_filename":"([^"]+)"',
                    r'"filename":"([^"]+)"',
                    r'<title>([^<]+)</title>',
                ]
                
                filename = "terabox_file"
                for pattern in filename_patterns:
                    match = re.search(pattern, text)
                    if match:
                        filename = match.group(1)
                        break
                
                # Extract size
                size_match = re.search(r'"size":(\d+)', text)
                size = int(size_match.group(1)) if size_match else None
                
                if download_url:
                    return download_url, sanitize_filename(filename), size
                
                # If no direct link found, return original URL
                return url, sanitize_filename(filename), size
        
        except Exception as e:
            logger.error(f"Terabox info error: {e}")
            return url, "terabox_file", None
    
    async def download_file(
        self,
        url: str,
        download_path: str,
        progress_message,
        filename: str = "downloading"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download file with progress updates"""
        try:
            session = await self.get_session()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return False, None, f"HTTP Error: {resp.status}"
                
                # Get file info
                total_size = int(resp.headers.get('Content-Length', 0))
                
                # Get filename from headers if not provided
                cd = resp.headers.get('Content-Disposition', '')
                if 'filename=' in cd:
                    header_filename = re.findall('filename="?([^";\n]+)"?', cd)
                    if header_filename:
                        filename = sanitize_filename(unquote(header_filename[0]))
                
                # Full file path
                file_path = os.path.join(download_path, filename)
                
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
                                    eta = int((total_size - downloaded) / speed) if speed > 0 else 0
                                    
                                    text = self.progress.get_download_progress_text(
                                        filename, downloaded, total_size, speed, eta
                                    )
                                    await progress_message.edit_text(text)
                                except Exception as e:
                                    logger.debug(f"Progress update error: {e}")
                
                return True, file_path, None
        
        except asyncio.CancelledError:
            return False, None, "Download cancelled"
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
            
            download_url, filename, size = await self.get_gdrive_download_url(file_id)
            
            if not download_url:
                return False, None, "Could not get download URL"
            
            return await self.download_file(
                download_url,
                download_path,
                progress_message,
                filename or "gdrive_file"
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
            download_url, filename, size = await self.get_terabox_download_info(url)
            
            if not download_url:
                return False, None, "Could not get download URL"
            
            return await self.download_file(
                download_url,
                download_path,
                progress_message,
                filename or "terabox_file"
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
            filename = url.split('/')[-1].split('?')[0]
            filename = unquote(filename) or "downloaded_file"
            
            return await self.download_file(
                url,
                download_path,
                progress_message,
                sanitize_filename(filename)
            )
        
        except Exception as e:
            logger.error(f"Direct download error: {e}")
            return False, None, str(e)
