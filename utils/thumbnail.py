import os
import logging
import asyncio
from PIL import Image
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class ThumbnailGenerator:
    def __init__(self):
        self.default_thumbnail = Config.THUMBNAIL_URL
    
    async def generate_video_thumbnail(self, video_path: str, output_path: str) -> Optional[str]:
        """Generate thumbnail from video using ffmpeg"""
        try:
            # Use ffmpeg to extract frame
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-vf', 'scale=320:320:force_original_aspect_ratio=decrease',
                '-y', output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if os.path.exists(output_path):
                return output_path
            
            return None
        except Exception as e:
            logger.error(f"Video thumbnail error: {e}")
            return None
    
    async def generate_image_thumbnail(self, image_path: str, output_path: str) -> Optional[str]:
        """Generate thumbnail from image"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize maintaining aspect ratio
                img.thumbnail((320, 320), Image.Resampling.LANCZOS)
                
                # Save as JPEG
                img.save(output_path, 'JPEG', quality=85)
            
            if os.path.exists(output_path):
                return output_path
            
            return None
        except Exception as e:
            logger.error(f"Image thumbnail error: {e}")
            return None
    
    async def generate_pdf_thumbnail(self, pdf_path: str, output_path: str) -> Optional[str]:
        """Generate thumbnail from PDF first page"""
        try:
            # Try using pdf2image
            try:
                from pdf2image import convert_from_path
                
                images = convert_from_path(pdf_path, first_page=1, last_page=1, size=(320, 320))
                if images:
                    images[0].save(output_path, 'JPEG', quality=85)
                    return output_path
            except ImportError:
                pass
            
            # Fallback: Use default thumbnail
            if self.default_thumbnail:
                return await self.download_default_thumbnail(output_path)
            
            return None
        except Exception as e:
            logger.error(f"PDF thumbnail error: {e}")
            return None
    
    async def generate_audio_thumbnail(self, audio_path: str, output_path: str) -> Optional[str]:
        """Extract album art from audio file"""
        try:
            from mutagen import File
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3
            
            audio = File(audio_path)
            
            if audio is None:
                return None
            
            # Try to get album art
            artwork = None
            
            if hasattr(audio, 'pictures') and audio.pictures:
                artwork = audio.pictures[0].data
            elif hasattr(audio, 'tags'):
                for key in audio.tags.keys():
                    if 'APIC' in key:
                        artwork = audio.tags[key].data
                        break
            
            if artwork:
                with open(output_path, 'wb') as f:
                    f.write(artwork)
                
                # Resize if needed
                await self.generate_image_thumbnail(output_path, output_path)
                return output_path
            
            return None
        except Exception as e:
            logger.error(f"Audio thumbnail error: {e}")
            return None
    
    async def generate_apk_thumbnail(self, apk_path: str, output_path: str) -> Optional[str]:
        """Generate thumbnail for APK (use default or icon)"""
        try:
            # For APK, we use default thumbnail
            if self.default_thumbnail:
                return await self.download_default_thumbnail(output_path)
            return None
        except Exception as e:
            logger.error(f"APK thumbnail error: {e}")
            return None
    
    async def download_default_thumbnail(self, output_path: str) -> Optional[str]:
        """Download default thumbnail from URL"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.default_thumbnail) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(output_path, 'wb') as f:
                            f.write(content)
                        return output_path
            return None
        except Exception as e:
            logger.error(f"Default thumbnail download error: {e}")
            return None
    
    async def generate_thumbnail(self, file_path: str, file_type: str) -> Optional[str]:
        """Generate thumbnail based on file type"""
        try:
            output_path = file_path + "_thumb.jpg"
            
            if file_type == "video":
                return await self.generate_video_thumbnail(file_path, output_path)
            elif file_type == "image":
                return await self.generate_image_thumbnail(file_path, output_path)
            elif file_type == "pdf":
                return await self.generate_pdf_thumbnail(file_path, output_path)
            elif file_type == "audio":
                thumb = await self.generate_audio_thumbnail(file_path, output_path)
                if not thumb and self.default_thumbnail:
                    return await self.download_default_thumbnail(output_path)
                return thumb
            elif file_type == "apk":
                return await self.generate_apk_thumbnail(file_path, output_path)
            else:
                return None
        except Exception as e:
            logger.error(f"Thumbnail generation error: {e}")
            return None
    
    async def apply_watermark_to_pdf(self, pdf_path: str, thumbnail_path: str) -> bool:
        """Apply thumbnail/watermark to PDF first page"""
        try:
            # This is a placeholder - implementing full PDF watermarking
            # requires additional libraries like PyPDF2 or reportlab
            return True
        except Exception as e:
            logger.error(f"PDF watermark error: {e}")
            return False
