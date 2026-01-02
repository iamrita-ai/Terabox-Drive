import os
import re
import shutil
import asyncio
import aiofiles
import logging
from typing import Optional, List
from urllib.parse import urlparse, unquote
from config import Config

logger = logging.getLogger(__name__)

# All supported video/download platforms
SUPPORTED_PLATFORMS = [
    # Google
    'drive.google.com', 'docs.google.com', 'drive.usercontent.google.com', 'storage.googleapis.com',
    
    # Terabox family
    'terabox.com', 'teraboxapp.com', '1024terabox.com', '1024tera.com',
    'nephobox.com', 'dm.nephobox.com', 'teraboxurl.com', 'terasharefile.com',
    'freeterabox.com', '4funbox.com', 'mirrobox.com', 'momerybox.com',
    'terabox.link', 'tbx.to',
    
    # Social Media
    'youtube.com', 'youtu.be', 'facebook.com', 'fb.watch', 'fb.com',
    'instagram.com', 'instagr.am', 'twitter.com', 'x.com',
    'tiktok.com', 'reddit.com', 'pinterest.com', 'linkedin.com',
    'snapchat.com', 'threads.net',
    
    # Video Platforms
    'vimeo.com', 'dailymotion.com', 'twitch.tv', 'bilibili.com',
    'nicovideo.jp', 'vlive.tv', 'weibo.com', 'douyin.com',
    'rumble.com', 'bitchute.com', 'odysee.com',
    'streamable.com', 'streamja.com', 'gfycat.com',
    
    # Education
    'udemy.com', 'coursera.org', 'skillshare.com', 'lynda.com',
    'pluralsight.com', 'edx.org', 'khanacademy.org', 'masterclass.com',
    
    # File Hosting
    'mediafire.com', 'mega.nz', 'ok.ru', 'vk.com',
    
    # Image/GIF
    'imgur.com', 'giphy.com',
]

def get_file_extension(filename: str) -> str:
    """Get file extension"""
    if not filename:
        return ''
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[-1].lower()
        if len(ext) <= 6:
            return ext
    return ''

def get_file_type(extension: str) -> str:
    """Get file type from extension"""
    if not extension:
        return "document"
    
    ext = extension.lower()
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpeg', '.mpg', '.ts']
    audio_exts = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus', '.amr']
    image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico']
    
    if ext in video_exts:
        return "video"
    elif ext in audio_exts:
        return "audio"
    elif ext in image_exts:
        return "image"
    elif ext == '.pdf':
        return "pdf"
    elif ext == '.apk':
        return "apk"
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
        return "archive"
    
    return "document"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    if not filename:
        return "downloaded_file"
    
    try:
        filename = unquote(filename)
    except:
        pass
    
    invalid_chars = '<>:"/\\|?*\x00\n\r\t'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    filename = filename.strip('. \t\n\r')
    
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    return filename if filename else "downloaded_file"

def extract_gdrive_id(url: str) -> Optional[str]:
    """Extract Google Drive file ID"""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/folders/([a-zA-Z0-9_-]+)',
        r'open\?id=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_gdrive_link(url: str) -> bool:
    """Check if Google Drive link"""
    patterns = ['drive.google.com', 'docs.google.com', 'drive.usercontent.google.com', 'storage.googleapis.com']
    return any(p in url.lower() for p in patterns)

def is_terabox_link(url: str) -> bool:
    """Check if Terabox link"""
    patterns = [
        'terabox.com', 'teraboxapp.com', '1024terabox.com', '1024tera.com',
        'nephobox.com', 'teraboxurl.com', 'terasharefile.com', 'freeterabox.com',
        '4funbox.com', 'mirrobox.com', 'momerybox.com', 'terabox.link', 'tbx.to',
    ]
    return any(p in url.lower() for p in patterns)

def is_supported_link(url: str) -> bool:
    """Check if URL is from any supported platform"""
    url_lower = url.lower()
    
    # Check known platforms
    if any(platform in url_lower for platform in SUPPORTED_PLATFORMS):
        return True
    
    # Check for direct file links
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        supported_exts = [
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.3gp',
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a',
            '.pdf', '.zip', '.rar', '.7z', '.apk',
            '.jpg', '.jpeg', '.png', '.gif', '.webp',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        ]
        if any(path.endswith(ext) for ext in supported_exts):
            return True
    except:
        pass
    
    # Any http/https link is potentially supported by yt-dlp
    if url.startswith('http://') or url.startswith('https://'):
        return True
    
    return False

def is_direct_link(url: str) -> bool:
    """Check if direct download link"""
    return is_supported_link(url)

def extract_links_from_text(text: str) -> List[str]:
    """Extract URLs from text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return [url.strip() for url in urls if url.strip()]

async def read_txt_file(file_path: str) -> List[str]:
    """Read links from txt file"""
    links = []
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
            links = extract_links_from_text(content)
    except Exception as e:
        logger.error(f"Error reading txt: {e}")
    return links

def create_download_dir(user_id: int) -> str:
    """Create download directory"""
    user_dir = os.path.join(Config.DOWNLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

async def cleanup_file(file_path: str):
    """Delete file"""
    try:
        if file_path and os.path.exists(file_path):
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
    except:
        pass

async def cleanup_user_dir(user_id: int):
    """Clean user directory"""
    try:
        user_dir = os.path.join(Config.DOWNLOAD_DIR, str(user_id))
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)
    except:
        pass

def get_readable_file_size(size_bytes: int) -> str:
    """Convert bytes to readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def generate_summary(results: dict) -> str:
    """Generate task summary"""
    total = results.get('total', 0)
    success = results.get('success', 0)
    failed = results.get('failed', 0)
    file_types = results.get('file_types', {})
    
    if success == total and total > 0:
        status_msg = "🎉 **All tasks completed successfully!**"
    elif success > 0:
        status_msg = "✨ **Tasks completed with some issues.**"
    else:
        status_msg = "😔 **All tasks failed.**"
    
    summary = f"""
{status_msg}

━━━━━━━━━━━━━━━━━━━━━━
📊 **Task Summary**
━━━━━━━━━━━━━━━━━━━━━━

✅ **Successful:** {success}
❌ **Failed:** {failed}
📁 **Total:** {total}

"""
    
    if file_types:
        summary += "📋 **File Types:**\n"
        for ftype, count in file_types.items():
            emoji = {'video': '🎬', 'audio': '🎵', 'image': '🖼️', 'pdf': '📄', 'apk': '📱', 'archive': '🗜️'}.get(ftype, '📁')
            summary += f"{emoji} {ftype.title()}: {count}\n"
    
    summary += """
━━━━━━━━━━━━━━━━━━━━━━

💝 **Thank you for using our bot!**
⭐ Share with your friends & enjoy!
"""
    
    return summary
