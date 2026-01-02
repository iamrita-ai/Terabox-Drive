import os
import re
import time
import json
import asyncio
import logging
import requests
import aiofiles
import aiohttp
from typing import Optional, Tuple, List, Dict
from urllib.parse import unquote, urlparse, parse_qs
from config import Config
from utils.progress import Progress
from utils.helpers import sanitize_filename, extract_gdrive_id

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self):
        self.progress = Progress()
        self.chunk_size = Config.CHUNK_SIZE
        
        # Terabox API endpoints
        self.TERABOX_API_URL = "https://www.terabox.com/api/shorturlinfo"
        self.TERABOX_LIST_URL = "https://www.terabox.com/share/list"
    
    def get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content-type"""
        content_type_map = {
            'video/mp4': '.mp4',
            'video/x-matroska': '.mkv',
            'video/webm': '.webm',
            'video/avi': '.avi',
            'video/quicktime': '.mov',
            'audio/mpeg': '.mp3',
            'audio/wav': '.wav',
            'audio/flac': '.flac',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'application/pdf': '.pdf',
            'application/zip': '.zip',
            'application/vnd.android.package-archive': '.apk',
        }
        ct = content_type.split(';')[0].strip().lower()
        return content_type_map.get(ct, '')
    
    def ensure_extension(self, filename: str, content_type: str = '', url: str = '') -> str:
        """Ensure filename has proper extension"""
        if not filename:
            filename = "downloaded_file"
        
        name, ext = os.path.splitext(filename)
        
        if ext and 2 <= len(ext) <= 5:
            return filename
        
        if content_type:
            ct_ext = self.get_extension_from_content_type(content_type)
            if ct_ext:
                return f"{name}{ct_ext}"
        
        if url:
            url_path = urlparse(url).path
            _, url_ext = os.path.splitext(url_path)
            if url_ext and 2 <= len(url_ext) <= 5:
                return f"{name}{url_ext}"
        
        if content_type and 'video' in content_type.lower():
            return f"{name}.mp4"
        
        return filename
    
    def extract_terabox_surl(self, url: str) -> Optional[str]:
        """Extract surl from Terabox/1024tera URL"""
        # Pattern 1: surl parameter
        match = re.search(r'surl=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: /s/ path
        match = re.search(r'/s/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        return None

    # ==================== SYNC DOWNLOAD ====================
    
    def download_file_sync(
        self,
        url: str,
        download_path: str,
        filename: str = "downloading",
        headers: dict = None,
        progress_callback = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download file using requests"""
        try:
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"📥 Downloading: {filename}")
            
            response = requests.get(
                url, 
                headers=request_headers, 
                stream=True, 
                timeout=3600, 
                allow_redirects=True
            )
            
            if response.status_code not in [200, 206]:
                return False, None, f"HTTP Error: {response.status_code}"
            
            total_size = int(response.headers.get('Content-Length', 0))
            content_type = response.headers.get('Content-Type', '')
            
            # Get filename from headers
            cd = response.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                matches = re.findall(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', cd)
                if matches:
                    filename = sanitize_filename(unquote(matches[0]))
            
            filename = self.ensure_extension(filename, content_type, url)
            
            file_path = os.path.join(download_path, filename)
            
            # Unique filename
            base, ext = os.path.splitext(file_path)
            counter = 1
            while os.path.exists(file_path):
                file_path = f"{base}_{counter}{ext}"
                counter += 1
            
            logger.info(f"📥 Saving to: {file_path} ({total_size} bytes)")
            
            downloaded = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(f"✅ Downloaded: {file_path}")
                return True, file_path, None
            else:
                return False, None, "Empty file"
        
        except requests.Timeout:
            return False, None, "Timeout"
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, None, str(e)

    # ==================== TERABOX API ====================
    
    def get_terabox_share_info(self, surl: str) -> Dict:
        """Get share info from Terabox API"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.terabox.com/',
                'Origin': 'https://www.terabox.com',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            # Try main Terabox API
            api_url = f"https://www.terabox.com/api/shorturlinfo?shorturl=1{surl}&root=1"
            
            logger.info(f"🔍 Calling Terabox API: {surl}")
            
            response = requests.get(api_url, headers=headers, timeout=30)
            data = response.json()
            
            if data.get('errno') == 0:
                return data
            
            # Try alternative endpoints
            alt_urls = [
                f"https://www.1024tera.com/api/shorturlinfo?shorturl=1{surl}&root=1",
                f"https://www.terabox.com/api/shorturlinfo?shorturl={surl}&root=1",
            ]
            
            for alt_url in alt_urls:
                try:
                    response = requests.get(alt_url, headers=headers, timeout=30)
                    data = response.json()
                    if data.get('errno') == 0:
                        return data
                except:
                    continue
            
            return {}
        
        except Exception as e:
            logger.error(f"API error: {e}")
            return {}
    
    def get_terabox_file_list(self, surl: str, share_id: str, uk: str, path: str = "/") -> List[Dict]:
        """Get file list from Terabox share"""
        files = []
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.terabox.com/',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            params = {
                'shorturl': f"1{surl}",
                'dir': path,
                'root': '1',
                'page': '1',
                'num': '100',
                'order': 'time',
            }
            
            if share_id:
                params['shareid'] = share_id
            if uk:
                params['uk'] = uk
            
            list_url = "https://www.terabox.com/share/list"
            
            response = requests.get(list_url, headers=headers, params=params, timeout=30)
            data = response.json()
            
            if data.get('errno') == 0:
                file_list = data.get('list', [])
                
                for item in file_list:
                    is_dir = item.get('isdir', 0)
                    
                    if is_dir == 0:
                        fname = item.get('server_filename', '') or item.get('filename', '') or 'file'
                        
                        if '.' not in fname:
                            fname = f"{fname}.mp4"
                        
                        dlink = item.get('dlink', '')
                        
                        files.append({
                            'filename': sanitize_filename(fname),
                            'size': item.get('size', 0),
                            'dlink': dlink,
                            'fs_id': item.get('fs_id', ''),
                            'path': item.get('path', '')
                        })
            
            logger.info(f"📁 Found {len(files)} files from API")
        
        except Exception as e:
            logger.error(f"File list error: {e}")
        
        return files
    
    def get_terabox_info_scrape(self, url: str) -> Tuple[Optional[str], Optional[str], List[Dict]]:
        """Scrape Terabox page for info"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            logger.info(f"🔍 Scraping: {url[:60]}...")
            
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            text = response.text
            
            # Extract download link
            download_url = None
            dlink_patterns = [
                r'"dlink"\s*:\s*"([^"]+)"',
                r'"downloadLink"\s*:\s*"([^"]+)"',
                r'href="(https://[^"]*d\.terabox[^"]*)"',
                r'href="(https://[^"]*1024tera[^"]*download[^"]*)"',
                r'"link"\s*:\s*"([^"]+download[^"]*)"',
            ]
            
            for pattern in dlink_patterns:
                match = re.search(pattern, text)
                if match:
                    download_url = match.group(1)
                    download_url = download_url.replace('\\/', '/').replace('\\u0026', '&')
                    if 'http' in download_url:
                        break
                    download_url = None
            
            # Extract filename
            filename = "terabox_file"
            fname_patterns = [
                r'"server_filename"\s*:\s*"([^"]+)"',
                r'"filename"\s*:\s*"([^"]+)"',
                r'"name"\s*:\s*"([^"]+)"',
                r'<title>([^<]+)</title>',
            ]
            
            for pattern in fname_patterns:
                match = re.search(pattern, text)
                if match:
                    fname = match.group(1).strip()
                    if fname and fname not in ["TeraBox", "1024Tera", "", "share", "分享"]:
                        filename = fname
                        break
            
            if '.' not in filename:
                filename = f"{filename}.mp4"
            
            # Extract file list
            files = []
            list_match = re.search(r'"list"\s*:\s*(\[[\s\S]*?\])\s*[,}]', text)
            
            if list_match:
                try:
                    json_str = list_match.group(1)
                    file_list = json.loads(json_str)
                    
                    for item in file_list:
                        is_dir = item.get('isdir', 0)
                        if is_dir == 0:
                            fname = item.get('server_filename') or item.get('filename') or item.get('name') or 'file'
                            if '.' not in fname:
                                fname = f"{fname}.mp4"
                            
                            dlink = item.get('dlink', '')
                            if dlink:
                                dlink = dlink.replace('\\/', '/').replace('\\u0026', '&')
                            
                            files.append({
                                'filename': sanitize_filename(fname),
                                'size': item.get('size', 0),
                                'dlink': dlink
                            })
                except:
                    pass
            
            logger.info(f"📄 Scraped: filename={filename}, dlink={'Yes' if download_url else 'No'}, files={len(files)}")
            
            return download_url, sanitize_filename(filename), files
        
        except Exception as e:
            logger.error(f"Scrape error: {e}")
            return None, "terabox_file.mp4", []

    # ==================== MAIN TERABOX DOWNLOAD ====================
    
    async def download_terabox(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Terabox/1024tera"""
        try:
            # Check if folder link
            is_folder = 'filelist' in url.lower() or ('path=' in url.lower() and 'path=%2F' not in url.lower())
            
            if is_folder:
                logger.info("📁 Terabox Folder detected")
                return True, "TERABOX_FOLDER:" + url, None
            
            # Update progress
            if progress_message:
                try:
                    await progress_message.edit_text("🔍 **Fetching Terabox info...**")
                except:
                    pass
            
            # Extract surl
            surl = self.extract_terabox_surl(url)
            logger.info(f"📎 Extracted surl: {surl}")
            
            # Try API first
            download_url = None
            filename = "terabox_file.mp4"
            
            if surl:
                share_info = self.get_terabox_share_info(surl)
                
                if share_info:
                    # Get file info from API response
                    file_list = share_info.get('list', [])
                    if file_list:
                        first_file = file_list[0]
                        filename = first_file.get('server_filename', '') or first_file.get('filename', '') or 'terabox_file'
                        download_url = first_file.get('dlink', '')
                        
                        if '.' not in filename:
                            filename = f"{filename}.mp4"
                        
                        filename = sanitize_filename(filename)
            
            # Fallback to scraping
            if not download_url:
                logger.info("📄 API failed, trying scrape...")
                download_url, filename, files = self.get_terabox_info_scrape(url)
                
                if files and not download_url:
                    download_url = files[0].get('dlink', '')
                    filename = files[0].get('filename', filename)
            
            # Download headers
            headers = {
                'Referer': 'https://www.terabox.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            # Update progress
            if progress_message:
                try:
                    await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`\n\n⏳ Please wait...")
                except:
                    pass
            
            # Download
            loop = asyncio.get_event_loop()
            
            if download_url and download_url.startswith('http'):
                logger.info(f"📥 Using dlink for: {filename}")
                success, file_path, error = await loop.run_in_executor(
                    None, self.download_file_sync, download_url, download_path, filename, headers, None
                )
            else:
                logger.info(f"📥 Trying direct URL: {filename}")
                success, file_path, error = await loop.run_in_executor(
                    None, self.download_file_sync, url, download_path, filename, headers, None
                )
            
            return success, file_path, error
        
        except Exception as e:
            logger.error(f"Terabox error: {e}")
            return False, None, str(e)
    
    async def get_terabox_folder_files(self, url: str) -> List[Dict]:
        """Get files from Terabox folder"""
        files = []
        
        try:
            surl = self.extract_terabox_surl(url)
            
            if not surl:
                logger.error("Could not extract surl from URL")
                return files
            
            logger.info(f"📁 Getting folder files for surl: {surl}")
            
            # Try API first
            share_info = self.get_terabox_share_info(surl)
            
            if share_info and share_info.get('errno') == 0:
                share_id = str(share_info.get('shareid', ''))
                uk = str(share_info.get('uk', ''))
                
                # Get file list
                files = self.get_terabox_file_list(surl, share_id, uk)
                
                if files:
                    return files
            
            # Fallback to scraping
            logger.info("📄 API failed, trying scrape for folder...")
            _, _, files = self.get_terabox_info_scrape(url)
            
            return files
        
        except Exception as e:
            logger.error(f"Folder files error: {e}")
            return files
    
    async def download_terabox_single_file(self, file_info: Dict, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download single file from folder"""
        try:
            dlink = file_info.get('dlink', '')
            filename = file_info.get('filename', 'terabox_file.mp4')
            
            if not dlink:
                return False, None, "No download link available"
            
            headers = {
                'Referer': 'https://www.terabox.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            if progress_message:
                try:
                    await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`\n\n⏳ Please wait...")
                except:
                    pass
            
            loop = asyncio.get_event_loop()
            success, file_path, error = await loop.run_in_executor(
                None, self.download_file_sync, dlink, download_path, filename, headers, None
            )
            
            return success, file_path, error
        
        except Exception as e:
            logger.error(f"Single file error: {e}")
            return False, None, str(e)

    # ==================== GOOGLE DRIVE ====================
    
    async def download_gdrive(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Google Drive"""
        try:
            # Direct links
            if 'drive.usercontent.google.com' in url or 'storage.googleapis.com' in url:
                logger.info("📁 Google Direct Link")
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self.download_file_sync, url, download_path, "google_file", {}, None
                )
            
            file_id = extract_gdrive_id(url)
            if not file_id:
                return False, None, "Invalid Google Drive URL"
            
            # Get download URL
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
            
            headers = {'Cookie': 'download_warning_token=1'}
            
            if progress_message:
                try:
                    await progress_message.edit_text("📥 **Downloading from Google Drive...**")
                except:
                    pass
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.download_file_sync, download_url, download_path, "gdrive_file", headers, None
            )
        
        except Exception as e:
            logger.error(f"GDrive error: {e}")
            return False, None, str(e)

    # ==================== DIRECT DOWNLOAD ====================
    
    async def download_direct(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from direct link"""
        try:
            parsed = urlparse(url)
            filename = parsed.path.split('/')[-1]
            filename = unquote(filename) if filename else "downloaded_file"
            
            if progress_message:
                try:
                    await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`")
                except:
                    pass
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.download_file_sync, url, download_path, sanitize_filename(filename), {}, None
            )
        
        except Exception as e:
            logger.error(f"Direct error: {e}")
            return False, None, str(e)
