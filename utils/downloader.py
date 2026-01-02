import os
import re
import time
import json
import asyncio
import logging
import requests
import subprocess
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
        
        # Supported platforms by yt-dlp
        self.YTDLP_SITES = [
            # Video Platforms
            'youtube.com', 'youtu.be',
            'facebook.com', 'fb.watch', 'fb.com',
            'instagram.com', 'instagr.am',
            'twitter.com', 'x.com',
            'tiktok.com',
            'vimeo.com',
            'dailymotion.com',
            'twitch.tv',
            'reddit.com',
            'pinterest.com',
            'linkedin.com',
            'snapchat.com',
            
            # Terabox & Mirrors
            'terabox.com', 'teraboxapp.com',
            '1024terabox.com', '1024tera.com',
            'nephobox.com', 'dm.nephobox.com',
            'teraboxurl.com', 'terasharefile.com',
            'freeterabox.com', '4funbox.com',
            'mirrobox.com', 'momerybox.com',
            
            # Education Platforms
            'udemy.com',
            'coursera.org',
            'skillshare.com',
            'lynda.com', 'linkedin.com/learning',
            'pluralsight.com',
            'edx.org',
            'khanacademy.org',
            'masterclass.com',
            
            # Streaming
            'bilibili.com',
            'nicovideo.jp',
            'vlive.tv',
            'weibo.com',
            'douyin.com',
            
            # Adult (if needed)
            # Add as needed
            
            # Others
            'mediafire.com',
            'mega.nz',
            'ok.ru',
            'vk.com',
            'rumble.com',
            'bitchute.com',
            'odysee.com',
            'streamable.com',
            'streamja.com',
            'gfycat.com',
            'imgur.com',
            'giphy.com',
        ]
        
        # Google Drive patterns
        self.GDRIVE_PATTERNS = [
            'drive.google.com',
            'docs.google.com',
            'drive.usercontent.google.com',
            'storage.googleapis.com',
        ]
    
    def is_ytdlp_supported(self, url: str) -> bool:
        """Check if URL is supported by yt-dlp"""
        url_lower = url.lower()
        
        # Check known sites
        for site in self.YTDLP_SITES:
            if site in url_lower:
                return True
        
        # Check for video extensions in URL (direct video links)
        video_exts = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m3u8', '.ts']
        for ext in video_exts:
            if ext in url_lower:
                return True
        
        return False
    
    def is_gdrive_link(self, url: str) -> bool:
        """Check if Google Drive link"""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.GDRIVE_PATTERNS)
    
    def is_direct_download(self, url: str) -> bool:
        """Check if direct download link"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            direct_exts = ['.pdf', '.zip', '.rar', '.7z', '.apk', '.exe', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
            return any(path.endswith(ext) for ext in direct_exts)
        except:
            return False
    
    def get_extension_from_content_type(self, content_type: str) -> str:
        """Get extension from content-type"""
        ct_map = {
            'video/mp4': '.mp4',
            'video/x-matroska': '.mkv',
            'video/webm': '.webm',
            'video/quicktime': '.mov',
            'audio/mpeg': '.mp3',
            'audio/wav': '.wav',
            'audio/flac': '.flac',
            'audio/mp4': '.m4a',
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
            if header[:4] == b'\x1a\x45\xdf\xa3':
                return '.webm'
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
            
            # HTML (error page)
            if b'<!DOCTYPE' in header or b'<html' in header.lower():
                return '.html'
            
            return None
        except:
            return None
    
    def validate_download(self, file_path: str, min_size: int = 10000) -> Tuple[bool, str]:
        """Validate downloaded file"""
        try:
            if not os.path.exists(file_path):
                return False, "File not found"
            
            size = os.path.getsize(file_path)
            if size < min_size:
                return False, f"File too small ({size} bytes)"
            
            detected = self.detect_file_type_from_bytes(file_path)
            if detected == '.html':
                return False, "Got HTML error page"
            
            return True, "OK"
        except Exception as e:
            return False, str(e)

    # ==================== YT-DLP DOWNLOAD ====================
    
    async def download_with_ytdlp(
        self,
        url: str,
        download_path: str,
        progress_message,
        prefer_audio: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download using yt-dlp (supports 1000+ sites)"""
        try:
            import yt_dlp
            
            if progress_message:
                try:
                    await progress_message.edit_text(
                        "📥 **Downloading with yt-dlp**\n\n"
                        "🔍 Extracting video info..."
                    )
                except:
                    pass
            
            # Output template
            output_template = os.path.join(download_path, '%(title)s.%(ext)s')
            
            # yt-dlp options
            ydl_opts = {
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': True,
                'ignoreerrors': False,
                'no_color': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
            }
            
            if prefer_audio:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }]
            else:
                # Best video up to 1080p (to avoid huge files)
                ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
                ydl_opts['merge_output_format'] = 'mp4'
            
            # Add cookies for Terabox
            if Config.TERABOX_COOKIE and any(x in url.lower() for x in ['terabox', '1024tera', 'nephobox']):
                # Create temp cookie file
                cookie_file = os.path.join(download_path, 'cookies.txt')
                self._create_cookie_file(cookie_file, Config.TERABOX_COOKIE)
                ydl_opts['cookiefile'] = cookie_file
            
            # Progress hook
            downloaded_file = [None]
            
            def progress_hook(d):
                if d['status'] == 'finished':
                    downloaded_file[0] = d.get('filename')
                elif d['status'] == 'downloading':
                    # Could update progress here if needed
                    pass
            
            ydl_opts['progress_hooks'] = [progress_hook]
            
            # Download
            logger.info(f"📥 yt-dlp downloading: {url[:60]}...")
            
            loop = asyncio.get_event_loop()
            
            def do_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if info:
                        # Get filename
                        if downloaded_file[0]:
                            return downloaded_file[0]
                        
                        # Try to find downloaded file
                        filename = ydl.prepare_filename(info)
                        
                        # Check for merged file
                        if os.path.exists(filename):
                            return filename
                        
                        # Check with .mp4 extension
                        mp4_file = os.path.splitext(filename)[0] + '.mp4'
                        if os.path.exists(mp4_file):
                            return mp4_file
                        
                        # Search in download path
                        for f in os.listdir(download_path):
                            if not f.endswith('.txt') and not f.startswith('.'):
                                full_path = os.path.join(download_path, f)
                                if os.path.isfile(full_path):
                                    return full_path
                    
                    return None
            
            file_path = await loop.run_in_executor(None, do_download)
            
            # Cleanup cookie file
            cookie_file = os.path.join(download_path, 'cookies.txt')
            if os.path.exists(cookie_file):
                os.remove(cookie_file)
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.info(f"✅ yt-dlp downloaded: {file_path} ({file_size} bytes)")
                
                # Validate
                is_valid, error = self.validate_download(file_path, min_size=1000)
                if not is_valid:
                    os.remove(file_path)
                    return False, None, error
                
                return True, file_path, None
            else:
                return False, None, "yt-dlp could not download the file"
        
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return False, None, str(e)
    
    def _create_cookie_file(self, filepath: str, cookie_string: str):
        """Create Netscape cookie file from cookie string"""
        try:
            lines = ["# Netscape HTTP Cookie File\n"]
            
            # Parse cookie string
            cookies = cookie_string.split(';')
            for cookie in cookies:
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    name = name.strip()
                    value = value.strip()
                    
                    # Netscape format: domain, flag, path, secure, expiry, name, value
                    lines.append(f".terabox.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
                    lines.append(f".1024tera.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
            
            with open(filepath, 'w') as f:
                f.writelines(lines)
        except Exception as e:
            logger.error(f"Cookie file error: {e}")

    # ==================== DIRECT/REQUESTS DOWNLOAD ====================
    
    def download_file_sync(
        self,
        url: str,
        download_path: str,
        filename: str = "downloading",
        headers: dict = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download file using requests"""
        try:
            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"📥 Direct downloading: {filename}")
            
            response = requests.get(url, headers=request_headers, stream=True, timeout=3600, allow_redirects=True)
            
            if response.status_code not in [200, 206]:
                return False, None, f"HTTP Error: {response.status_code}"
            
            total_size = int(response.headers.get('Content-Length', 0))
            content_type = response.headers.get('Content-Type', '')
            
            # Check for HTML error
            if 'text/html' in content_type.lower() and total_size < 50000:
                return False, None, "Got error page - file not available"
            
            # Get filename from headers
            cd = response.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                matches = re.findall(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)', cd)
                if matches:
                    filename = sanitize_filename(unquote(matches[0]))
            
            # Fix extension
            name, ext = os.path.splitext(filename)
            if not ext or len(ext) > 6:
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
            is_valid, error = self.validate_download(file_path)
            if not is_valid:
                try:
                    os.remove(file_path)
                except:
                    pass
                return False, None, error
            
            # Fix extension based on content
            detected = self.detect_file_type_from_bytes(file_path)
            if detected and detected not in ['.html']:
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

    # ==================== GOOGLE DRIVE ====================
    
    async def download_gdrive(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Google Drive"""
        try:
            # Direct links
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

    # ==================== MAIN DOWNLOAD ROUTER ====================
    
    async def download(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Main download router - automatically selects best method"""
        try:
            url = url.strip()
            
            if progress_message:
                try:
                    await progress_message.edit_text("🔍 **Analyzing link...**")
                except:
                    pass
            
            # Route 1: Google Drive
            if self.is_gdrive_link(url):
                logger.info("📁 Route: Google Drive")
                return await self.download_gdrive(url, download_path, progress_message)
            
            # Route 2: Direct download (non-video files)
            if self.is_direct_download(url):
                logger.info("📁 Route: Direct Download")
                if progress_message:
                    try:
                        await progress_message.edit_text("📥 **Downloading file...**")
                    except:
                        pass
                
                filename = urlparse(url).path.split('/')[-1]
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self.download_file_sync, url, download_path, sanitize_filename(unquote(filename)), {}
                )
            
            # Route 3: yt-dlp for video platforms
            if self.is_ytdlp_supported(url):
                logger.info("📁 Route: yt-dlp (video platform)")
                return await self.download_with_ytdlp(url, download_path, progress_message)
            
            # Route 4: Try yt-dlp anyway (it supports many sites)
            logger.info("📁 Route: Trying yt-dlp as fallback...")
            success, file_path, error = await self.download_with_ytdlp(url, download_path, progress_message)
            
            if success:
                return True, file_path, None
            
            # Route 5: Fallback to direct download
            logger.info("📁 Route: Fallback to direct download")
            if progress_message:
                try:
                    await progress_message.edit_text("📥 **Trying direct download...**")
                except:
                    pass
            
            filename = urlparse(url).path.split('/')[-1] or "downloaded_file"
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.download_file_sync, url, download_path, sanitize_filename(unquote(filename)), {}
            )
        
        except Exception as e:
            logger.error(f"Download router error: {e}")
            return False, None, str(e)

    # ==================== TERABOX (Legacy for folders) ====================
    
    def extract_terabox_surl(self, url: str) -> Optional[str]:
        """Extract surl from Terabox URL"""
        patterns = [
            r'[?&]surl=([a-zA-Z0-9_-]+)',
            r'/s/1?([a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def download_terabox(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download from Terabox - uses yt-dlp"""
        # Check folder
        url_lower = url.lower()
        is_folder = 'filelist' in url_lower or ('path=' in url_lower and 'path=%2f' not in url_lower)
        
        if is_folder:
            logger.info("📁 Terabox Folder detected")
            return True, "TERABOX_FOLDER:" + url, None
        
        # Use yt-dlp for single file
        return await self.download_with_ytdlp(url, download_path, progress_message)
    
    async def get_terabox_folder_files(self, url: str) -> List[Dict]:
        """Get Terabox folder files (requires cookie)"""
        files = []
        
        if not Config.TERABOX_COOKIE:
            logger.warning("No TERABOX_COOKIE for folder")
            return files
        
        surl = self.extract_terabox_surl(url)
        if not surl:
            return files
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': Config.TERABOX_COOKIE,
        }
        
        for base in ["https://www.terabox.com", "https://www.1024tera.com"]:
            try:
                # Get share info
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
        
        return files
    
    async def download_terabox_single_file(self, file_info: Dict, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download single file from Terabox folder"""
        dlink = file_info.get('dlink', '')
        filename = file_info.get('filename', 'file')
        
        if not dlink:
            return False, None, "No download link"
        
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
    
    # Legacy methods for compatibility
    async def download_direct(self, url: str, download_path: str, progress_message) -> Tuple[bool, Optional[str], Optional[str]]:
        return await self.download(url, download_path, progress_message)
