import os
import re
import time
import json
import asyncio
import logging
import requests
from typing import Optional, Tuple, List, Dict
from urllib.parse import unquote, urlparse, quote
from config import Config
from utils.progress import Progress
from utils.helpers import sanitize_filename, extract_gdrive_id

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self):
        self.progress = Progress()
        self.chunk_size = Config.CHUNK_SIZE
        
        # Third-party Terabox APIs (free services)
        self.TERABOX_THIRD_PARTY_APIS = [
            "https://teraboxdownloader.online/api/download?url=",
            "https://terabox.udayscriptsx.workers.dev/?url=",
            "https://tera.instavideosave.com/?url=",
            "https://teradl-api.dapuntaratya.com/generate?url=",
        ]
    
    def extract_terabox_surl(self, url: str) -> Optional[str]:
        """Extract surl from Terabox URL"""
        patterns = [
            r'[?&]surl=([a-zA-Z0-9_-]+)',
            r'/s/1?([a-zA-Z0-9_-]+)',
            r'tbx\.to/([a-zA-Z0-9_-]+)',
            r'terabox\.link/([a-zA-Z0-9_-]+)',
            r'/sharing/(?:link|video)\?surl=([a-zA-Z0-9_-]+)',
            r'/wap/share/filelist\?surl=([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def normalize_terabox_url(self, url: str) -> str:
        """Normalize any Terabox URL to standard format"""
        surl = self.extract_terabox_surl(url)
        if surl:
            clean_surl = surl.lstrip('1') if len(surl) > 20 else surl
            return f"https://www.terabox.com/s/1{clean_surl}"
        return url
    
    def get_extension_from_content_type(self, content_type: str) -> str:
        """Get extension from content-type"""
        ct_map = {
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
        return ct_map.get(ct, '')
    
    def detect_file_type_from_bytes(self, file_path: str) -> Optional[str]:
        """Detect file type from magic bytes"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            # Video
            if b'ftyp' in header[:12]:
                return '.mp4'
            if header[:4] == b'\x1a\x45\xdf\xa3':
                return '.mkv'
            if header[:4] == b'RIFF' and header[8:12] == b'AVI ':
                return '.avi'
            if header[:3] == b'FLV':
                return '.flv'
            
            # Audio
            if header[:3] == b'ID3' or header[:2] in [b'\xff\xfb', b'\xff\xfa']:
                return '.mp3'
            if header[:4] == b'fLaC':
                return '.flac'
            if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                return '.wav'
            if header[:4] == b'OggS':
                return '.ogg'
            
            # Image
            if header[:2] == b'\xff\xd8':
                return '.jpg'
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                return '.png'
            if header[:6] in [b'GIF87a', b'GIF89a']:
                return '.gif'
            
            # Document
            if header[:4] == b'%PDF':
                return '.pdf'
            if header[:4] == b'PK\x03\x04':
                return '.zip'
            if header[:6] == b'Rar!\x1a\x07':
                return '.rar'
            
            # HTML (error)
            if b'<!DOCTYPE' in header or b'<html' in header.lower():
                return '.html'
            
            return None
        except:
            return None
    
    def validate_download(self, file_path: str) -> Tuple[bool, str]:
        """Validate downloaded file"""
        try:
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            file_size = os.path.getsize(file_path)
            
            if file_size < 1000:
                return False, "File too small - likely error page"
            
            detected = self.detect_file_type_from_bytes(file_path)
            if detected == '.html':
                return False, "Got HTML error page instead of file"
            
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def download_file_sync(
        self,
        url: str,
        download_path: str,
        filename: str = "downloading",
        headers: dict = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download file"""
        try:
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"📥 Downloading: {filename}")
            
            response = requests.get(url, headers=request_headers, stream=True, timeout=3600, allow_redirects=True)
            
            if response.status_code not in [200, 206]:
                return False, None, f"HTTP Error: {response.status_code}"
            
            total_size = int(response.headers.get('Content-Length', 0))
            content_type = response.headers.get('Content-Type', '')
            
            # Check for HTML error
            if 'text/html' in content_type.lower() and total_size < 10000:
                return False, None, "Received error page - file not available"
            
            # Get filename from headers
            cd = response.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                matches = re.findall(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', cd)
                if matches:
                    filename = sanitize_filename(unquote(matches[0]))
            
            # Fix extension if missing
            name, ext = os.path.splitext(filename)
            if not ext or len(ext) > 5:
                ct_ext = self.get_extension_from_content_type(content_type)
                if ct_ext:
                    filename = f"{name}{ct_ext}"
            
            file_path = os.path.join(download_path, filename)
            
            # Unique filename
            base, ext = os.path.splitext(file_path)
            counter = 1
            while os.path.exists(file_path):
                file_path = f"{base}_{counter}{ext}"
                counter += 1
            
            logger.info(f"📥 Saving: {file_path} ({total_size} bytes)")
            
            downloaded = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            # Validate
            is_valid, error_msg = self.validate_download(file_path)
            if not is_valid:
                try:
                    os.remove(file_path)
                except:
                    pass
                return False, None, error_msg
            
            # Fix extension from content
            detected = self.detect_file_type_from_bytes(file_path)
            if detected and detected != '.html':
                current_ext = os.path.splitext(file_path)[1].lower()
                if not current_ext or current_ext != detected:
                    new_path = os.path.splitext(file_path)[0] + detected
                    try:
                        os.rename(file_path, new_path)
                        file_path = new_path
                    except:
                        pass
            
            final_size = os.path.getsize(file_path)
            logger.info(f"✅ Downloaded: {file_path} ({final_size} bytes)")
            
            return True, file_path, None
        
        except requests.Timeout:
            return False, None, "Download timeout"
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, None, str(e)

    # ==================== TERABOX THIRD-PARTY API ====================
    
    def try_third_party_api(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Try third-party APIs to get download link"""
        normalized_url = self.normalize_terabox_url(url)
        
        for api_base in self.TERABOX_THIRD_PARTY_APIS:
            try:
                api_url = api_base + quote(normalized_url, safe='')
                logger.info(f"🔍 Trying API: {api_base[:40]}...")
                
                response = requests.get(api_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json() if response.headers.get('Content-Type', '').startswith('application/json') else {}
                    
                    # Different API response formats
                    download_url = (
                        data.get('download_link') or 
                        data.get('downloadLink') or 
                        data.get('dlink') or 
                        data.get('url') or
                        data.get('data', {}).get('download_link') or
                        data.get('data', {}).get('dlink') or
                        data.get('result', {}).get('download_link')
                    )
                    
                    filename = (
                        data.get('filename') or 
                        data.get('file_name') or 
                        data.get('name') or
                        data.get('data', {}).get('filename') or
                        "terabox_file"
                    )
                    
                    if download_url and download_url.startswith('http'):
                        logger.info(f"✅ Got download link from third-party API")
                        return download_url, sanitize_filename(filename)
            
            except Exception as e:
                logger.debug(f"API error: {e}")
                continue
        
        return None, None
    
    # ==================== TERABOX OFFICIAL API ====================
    
    def get_terabox_official_api(self, surl: str) -> Tuple[Optional[str], Optional[str]]:
        """Try official Terabox API"""
        if not Config.TERABOX_COOKIE:
            logger.info("⚠️ No TERABOX_COOKIE set")
            return None, None
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': Config.TERABOX_COOKIE,
            'Referer': 'https://www.terabox.com/',
        }
        
        api_bases = [
            "https://www.terabox.com",
            "https://www.1024tera.com",
            "https://teraboxapp.com",
        ]
        
        for base in api_bases:
            for prefix in ['1', '']:
                try:
                    api_url = f"{base}/api/shorturlinfo?shorturl={prefix}{surl}&root=1"
                    response = requests.get(api_url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get('errno') == 0:
                            file_list = data.get('list', [])
                            if file_list:
                                first = file_list[0]
                                dlink = first.get('dlink', '')
                                fname = first.get('server_filename') or first.get('filename') or 'terabox_file'
                                
                                if dlink:
                                    logger.info(f"✅ Got link from official API")
                                    return dlink, sanitize_filename(fname)
                except:
                    continue
        
        return None, None
    
    def scrape_terabox_page(self, url: str) -> Tuple[Optional[str], str]:
        """Scrape Terabox page directly"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            normalized = self.normalize_terabox_url(url)
            response = requests.get(normalized, headers=headers, timeout=30)
            text = response.text
            
            # Find dlink
            dlink = None
            for pattern in [r'"dlink"\s*:\s*"([^"]+)"', r'"downloadLink"\s*:\s*"([^"]+)"']:
                match = re.search(pattern, text)
                if match:
                    dlink = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
                    if dlink.startswith('http'):
                        break
                    dlink = None
            
            # Find filename
            filename = "terabox_file"
            for pattern in [r'"server_filename"\s*:\s*"([^"]+)"', r'"filename"\s*:\s*"([^"]+)"']:
                match = re.search(pattern, text)
                if match:
                    fname = match.group(1).strip()
                    if fname and len(fname) > 2:
                        filename = fname
                        break
            
            return dlink, sanitize_filename(filename)
        
        except Exception as e:
            logger.error(f"Scrape error: {e}")
            return None, "terabox_file"

    # ==================== MAIN TERABOX DOWNLOAD ====================
    
    async def download_terabox(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Terabox - tries multiple methods"""
        try:
            # Check folder
            url_lower = url.lower()
            is_folder = 'filelist' in url_lower or ('path=' in url_lower and 'path=%2f' not in url_lower)
            
            if is_folder:
                logger.info("📁 Terabox Folder detected")
                return True, "TERABOX_FOLDER:" + url, None
            
            if progress_message:
                try:
                    await progress_message.edit_text("🔍 **Fetching Terabox info...**\n\n⏳ Trying multiple methods...")
                except:
                    pass
            
            surl = self.extract_terabox_surl(url)
            logger.info(f"📎 Extracted surl: {surl}")
            
            download_url = None
            filename = "terabox_file"
            
            # Method 1: Third-party APIs (most reliable without cookies)
            logger.info("🔄 Method 1: Third-party APIs...")
            download_url, filename = self.try_third_party_api(url)
            
            # Method 2: Official API with cookies
            if not download_url and surl:
                logger.info("🔄 Method 2: Official API...")
                download_url, filename = self.get_terabox_official_api(surl)
            
            # Method 3: Page scraping
            if not download_url:
                logger.info("🔄 Method 3: Page scraping...")
                download_url, filename = self.scrape_terabox_page(url)
            
            # Check if we got a download URL
            if not download_url:
                error_msg = "❌ Could not get download link.\n\n"
                error_msg += "**Possible solutions:**\n"
                error_msg += "1️⃣ Add `TERABOX_COOKIE` to environment\n"
                error_msg += "2️⃣ Try a different Terabox link\n"
                error_msg += "3️⃣ The file may be private/deleted"
                return False, None, error_msg
            
            # Prepare headers
            headers = {
                'Referer': 'https://www.terabox.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            if progress_message:
                try:
                    await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`\n\n⏳ Please wait...")
                except:
                    pass
            
            # Download
            loop = asyncio.get_event_loop()
            success, file_path, error = await loop.run_in_executor(
                None, self.download_file_sync, download_url, download_path, filename, headers
            )
            
            return success, file_path, error
        
        except Exception as e:
            logger.error(f"Terabox error: {e}")
            return False, None, str(e)
    
    async def get_terabox_folder_files(self, url: str) -> List[Dict]:
        """Get folder files"""
        files = []
        
        surl = self.extract_terabox_surl(url)
        if not surl:
            return files
        
        # Try official API
        if Config.TERABOX_COOKIE:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Cookie': Config.TERABOX_COOKIE,
            }
            
            for base in ["https://www.terabox.com", "https://www.1024tera.com"]:
                try:
                    # Get share info first
                    info_url = f"{base}/api/shorturlinfo?shorturl=1{surl}&root=1"
                    response = requests.get(info_url, headers=headers, timeout=30)
                    data = response.json()
                    
                    if data.get('errno') == 0:
                        shareid = str(data.get('shareid', ''))
                        uk = str(data.get('uk', ''))
                        
                        # Get file list
                        list_url = f"{base}/share/list"
                        params = {
                            'shorturl': f"1{surl}",
                            'dir': '/',
                            'root': '1',
                            'page': '1',
                            'num': '100',
                            'shareid': shareid,
                            'uk': uk,
                        }
                        
                        response = requests.get(list_url, headers=headers, params=params, timeout=30)
                        data = response.json()
                        
                        if data.get('errno') == 0:
                            for item in data.get('list', []):
                                if item.get('isdir', 0) == 0:
                                    files.append({
                                        'filename': sanitize_filename(item.get('server_filename', 'file')),
                                        'size': item.get('size', 0),
                                        'dlink': item.get('dlink', ''),
                                    })
                            
                            if files:
                                return files
                except:
                    continue
        
        # Fallback: scrape page
        try:
            normalized = self.normalize_terabox_url(url)
            headers = {'User-Agent': 'Mozilla/5.0'}
            if Config.TERABOX_COOKIE:
                headers['Cookie'] = Config.TERABOX_COOKIE
            
            response = requests.get(normalized, headers=headers, timeout=30)
            text = response.text
            
            match = re.search(r'"list"\s*:\s*(\[[\s\S]*?\])\s*[,}]', text)
            if match:
                try:
                    file_list = json.loads(match.group(1))
                    for item in file_list:
                        if item.get('isdir', 0) == 0:
                            dlink = item.get('dlink', '').replace('\\/', '/')
                            files.append({
                                'filename': sanitize_filename(item.get('server_filename', 'file')),
                                'size': item.get('size', 0),
                                'dlink': dlink,
                            })
                except:
                    pass
        except:
            pass
        
        return files
    
    async def download_terabox_single_file(self, file_info: Dict, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download single file from folder"""
        dlink = file_info.get('dlink', '')
        filename = file_info.get('filename', 'file')
        
        if not dlink:
            return False, None, "No download link for this file"
        
        headers = {
            'Referer': 'https://www.terabox.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        if Config.TERABOX_COOKIE:
            headers['Cookie'] = Config.TERABOX_COOKIE
        
        if progress_message:
            try:
                await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`")
            except:
                pass
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.download_file_sync, dlink, download_path, filename, headers
        )

    # ==================== GOOGLE DRIVE ====================
    
    async def download_gdrive(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Google Drive"""
        try:
            if 'drive.usercontent.google.com' in url or 'storage.googleapis.com' in url:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self.download_file_sync, url, download_path, "google_file", {}
                )
            
            file_id = extract_gdrive_id(url)
            if not file_id:
                return False, None, "Invalid Google Drive URL"
            
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
            
            if progress_message:
                try:
                    await progress_message.edit_text("📥 **Downloading from Google Drive...**")
                except:
                    pass
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.download_file_sync, download_url, download_path, "gdrive_file", {}
            )
        except Exception as e:
            return False, None, str(e)

    async def download_direct(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from direct link"""
        try:
            filename = urlparse(url).path.split('/')[-1]
            filename = unquote(filename) if filename else "downloaded_file"
            
            if progress_message:
                try:
                    await progress_message.edit_text(f"📥 **Downloading**\n\n`{filename}`")
                except:
                    pass
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.download_file_sync, url, download_path, sanitize_filename(filename), {}
            )
        except Exception as e:
            return False, None, str(e)
