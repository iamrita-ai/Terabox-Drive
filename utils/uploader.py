import os
import time
import logging
import asyncio
from typing import Optional, Tuple
from pyrogram import Client
from pyrogram.types import Message
from config import Config
from utils.progress import Progress
from utils.helpers import get_readable_file_size, get_file_extension
from utils.thumbnail import ThumbnailGenerator

logger = logging.getLogger(__name__)

class Uploader:
    def __init__(self):
        self.progress = Progress()
        self.thumbnail_gen = ThumbnailGenerator()
    
    def detect_file_type_from_content(self, file_path: str) -> str:
        """Detect ACTUAL file type from file content (magic bytes)"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            # Video
            if header[:4] == b'\x00\x00\x00\x1c' or header[:4] == b'\x00\x00\x00\x20':
                if b'ftyp' in header[:12]:
                    return "video"
            if header[:4] == b'\x1a\x45\xdf\xa3':  # MKV/WebM
                return "video"
            if header[:4] == b'RIFF' and header[8:12] == b'AVI ':
                return "video"
            if header[:3] == b'FLV':
                return "video"
            
            # Audio
            if header[:3] == b'ID3' or header[:2] == b'\xff\xfb' or header[:2] == b'\xff\xfa':
                return "audio"
            if header[:4] == b'fLaC':
                return "audio"
            if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                return "audio"
            if header[:4] == b'OggS':
                return "audio"
            if b'ftyp' in header[:12] and b'M4A' in header[:12]:
                return "audio"
            
            # Image
            if header[:2] == b'\xff\xd8':
                return "image"
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                return "image"
            if header[:6] in [b'GIF87a', b'GIF89a']:
                return "image"
            if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                return "image"
            if header[:2] == b'BM':
                return "image"
            
            # PDF
            if header[:4] == b'%PDF':
                return "pdf"
            
            # Archive
            if header[:4] == b'PK\x03\x04':
                return "archive"
            if header[:6] == b'Rar!\x1a\x07':
                return "archive"
            if header[:6] == b'7z\xbc\xaf\x27\x1c':
                return "archive"
            
            # APK (also starts with PK, check extension)
            ext = get_file_extension(file_path).lower()
            if ext == '.apk':
                return "apk"
            
            # Fallback to extension
            return self.get_type_from_extension(ext)
        
        except Exception as e:
            logger.error(f"Content detection error: {e}")
            return "document"
    
    def get_type_from_extension(self, ext: str) -> str:
        """Get file type from extension"""
        ext = ext.lower()
        
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
    
    async def get_video_metadata(self, file_path: str) -> Tuple[int, int, int]:
        """Get video duration, width, height"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            if stdout:
                import json
                data = json.loads(stdout.decode())
                
                duration = int(float(data.get('format', {}).get('duration', 0)))
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width', 0)
                        height = stream.get('height', 0)
                        if not duration:
                            duration = int(float(stream.get('duration', 0)))
                        return duration, width, height
            
            return 0, 0, 0
        except:
            return 0, 0, 0
    
    async def get_audio_duration(self, file_path: str) -> int:
        """Get audio duration"""
        try:
            from mutagen import File
            audio = File(file_path)
            if audio and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                return int(audio.info.length)
            return 0
        except:
            return 0
    
    async def upload_file(
        self,
        client: Client,
        file_path: str,
        chat_id: int,
        progress_message: Message,
        caption: str = None,
        reply_to_message_id: int = None,
        message_thread_id: int = None,
        custom_thumbnail: str = None,
        file_type: str = None  # This is ignored - we detect from content
    ) -> Tuple[bool, Optional[Message], Optional[str]]:
        """Upload file - detects type from actual content"""
        try:
            if not os.path.exists(file_path):
                return False, None, "File not found"
            
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # DETECT ACTUAL FILE TYPE FROM CONTENT
            actual_type = self.detect_file_type_from_content(file_path)
            
            logger.info(f"⬆️ Uploading: {filename} ({get_readable_file_size(file_size)}) as {actual_type}")
            
            if caption is None:
                caption = f"📁 **{filename}**\n📊 Size: {get_readable_file_size(file_size)}"
            
            # Generate thumbnail only for video/audio
            thumbnail = None
            if custom_thumbnail and os.path.exists(custom_thumbnail):
                thumbnail = custom_thumbnail
            elif actual_type in ["video", "audio"]:
                thumbnail = await self.thumbnail_gen.generate_thumbnail(file_path, actual_type)
            
            # Progress
            start_time = time.time()
            
            async def progress_callback(current, total):
                try:
                    if self.progress.should_update():
                        elapsed = time.time() - start_time
                        speed = current / elapsed if elapsed > 0 else 0
                        eta = int((total - current) / speed) if speed > 0 else 0
                        
                        text = self.progress.get_upload_progress_text(filename, current, total, speed, eta)
                        await progress_message.edit_text(text)
                except:
                    pass
            
            sent_message = None
            
            # ==================== UPLOAD BASED ON ACTUAL TYPE ====================
            
            if actual_type == "video":
                logger.info("🎬 Uploading as VIDEO")
                
                duration, width, height = await self.get_video_metadata(file_path)
                
                try:
                    sent_message = await client.send_video(
                        chat_id=chat_id,
                        video=file_path,
                        caption=caption,
                        duration=duration,
                        width=width,
                        height=height,
                        thumb=thumbnail,
                        supports_streaming=True,
                        reply_to_message_id=reply_to_message_id,
                        progress=progress_callback
                    )
                except Exception as e:
                    logger.error(f"Video upload error: {e}")
                    # Fallback to document
                    sent_message = await client.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=caption,
                        thumb=thumbnail,
                        reply_to_message_id=reply_to_message_id,
                        progress=progress_callback
                    )
            
            elif actual_type == "audio":
                logger.info("🎵 Uploading as AUDIO")
                
                duration = await self.get_audio_duration(file_path)
                
                try:
                    sent_message = await client.send_audio(
                        chat_id=chat_id,
                        audio=file_path,
                        caption=caption,
                        duration=duration,
                        thumb=thumbnail,
                        reply_to_message_id=reply_to_message_id,
                        progress=progress_callback
                    )
                except Exception as e:
                    logger.error(f"Audio upload error: {e}")
                    sent_message = await client.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=caption,
                        reply_to_message_id=reply_to_message_id,
                        progress=progress_callback
                    )
            
            elif actual_type == "image":
                logger.info("🖼️ Uploading as IMAGE")
                
                if file_size < 10 * 1024 * 1024:  # Under 10 MB
                    try:
                        sent_message = await client.send_photo(
                            chat_id=chat_id,
                            photo=file_path,
                            caption=caption,
                            reply_to_message_id=reply_to_message_id,
                            progress=progress_callback
                        )
                    except:
                        sent_message = await client.send_document(
                            chat_id=chat_id,
                            document=file_path,
                            caption=caption,
                            reply_to_message_id=reply_to_message_id,
                            progress=progress_callback
                        )
                else:
                    sent_message = await client.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=caption,
                        reply_to_message_id=reply_to_message_id,
                        progress=progress_callback
                    )
            
            else:
                # PDF, APK, Archive, Document - send as document
                logger.info(f"📄 Uploading as DOCUMENT ({actual_type})")
                
                sent_message = await client.send_document(
                    chat_id=chat_id,
                    document=file_path,
                    caption=caption,
                    thumb=thumbnail,
                    reply_to_message_id=reply_to_message_id,
                    progress=progress_callback
                )
            
            # Cleanup thumbnail
            if thumbnail and os.path.exists(thumbnail) and thumbnail != custom_thumbnail:
                try:
                    os.remove(thumbnail)
                except:
                    pass
            
            return True, sent_message, None
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False, None, str(e)
    
    async def send_log(
        self,
        client: Client,
        user_id: int,
        username: str,
        url: str,
        filename: str,
        status: str,
        error: str = None
    ):
        """Send log to log channel"""
        try:
            emoji = "✅" if status == "success" else "❌"
            url_display = url[:80] + "..." if len(url) > 80 else url
            
            log_text = f"""
{emoji} **File {'Uploaded' if status == 'success' else 'Failed'}**

👤 **User:** @{username or 'None'} (`{user_id}`)
📁 **File:** `{filename}`
🔗 **Link:** `{url_display}`
"""
            if error:
                log_text += f"\n❌ **Error:** `{error[:100]}`"
            
            await client.send_message(Config.LOG_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log error: {e}")
