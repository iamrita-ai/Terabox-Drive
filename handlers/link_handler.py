import os
import uuid
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from database import db, user_db
from handlers.start import force_sub_check
from utils.queue_manager import queue_manager, Task
from utils.downloader import Downloader
from utils.uploader import Uploader
from utils.helpers import (
    is_gdrive_link, is_terabox_link, is_direct_link,
    extract_links_from_text, create_download_dir, cleanup_file,
    get_file_extension, get_file_type, generate_summary
)

logger = logging.getLogger(__name__)

downloader = Downloader()
uploader = Uploader()

# Link filter
def link_filter(_, __, message: Message):
    """Filter for messages containing links"""
    if not message.text:
        return False
    
    text = message.text.lower()
    return any([
        'drive.google.com' in text,
        'terabox' in text,
        'http://' in text,
        'https://' in text
    ])

link_filter = filters.create(link_filter)

@Client.on_message(filters.private & link_filter & ~filters.command(["start", "help", "setting", "cancel", "broadcast", "premium", "removepremium"]))
async def handle_private_link(client: Client, message: Message):
    """Handle links in private chat"""
    await process_links(client, message)

@Client.on_message(filters.group & link_filter)
async def handle_group_link(client: Client, message: Message):
    """Handle links in group (when bot is mentioned or replied to)"""
    # Check if bot is mentioned or message is reply to bot
    bot_info = await client.get_me()
    is_mentioned = f"@{bot_info.username}" in (message.text or "")
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    if is_mentioned or is_reply_to_bot:
        await process_links(client, message, is_group=True)

async def process_links(client: Client, message: Message, is_group: bool = False):
    """Process links from message"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    chat_id = message.chat.id
    
    # Get topic ID if in group topic
    topic_id = None
    if is_group and message.message_thread_id:
        topic_id = message.message_thread_id
    
    # Add user to database
    await db.add_user(user_id, username, first_name)
    
    # Check if banned
    if await db.is_user_banned(user_id):
        return await message.reply_text("❌ You are banned from using this bot!")
    
    # Check force subscribe (only in private)
    if not is_group and not await force_sub_check(client, user_id):
        return await message.reply_text(
            "⚠️ Please join our channel first!\n\n"
            f"🔗 {Config.FORCE_SUB_LINK}"
        )
    
    # Check daily limit
    can_use, remaining = await user_db.can_use_bot(user_id)
    if not can_use:
        return await message.reply_text(
            "❌ **Daily Limit Reached!**\n\n"
            f"You've used all {Config.FREE_DAILY_LIMIT} free tasks for today.\n\n"
            "💎 Upgrade to Premium for unlimited access!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💻 Get Premium", url=Config.OWNER_CONTACT)]
            ])
        )
    
    # Extract links
    links = extract_links_from_text(message.text)
    
    if not links:
        return await message.reply_text("❌ No valid links found in your message!")
    
    # Filter supported links
    supported_links = []
    for link in links:
        if is_gdrive_link(link) or is_terabox_link(link) or is_direct_link(link):
            supported_links.append(link)
    
    if not supported_links:
        return await message.reply_text(
            "❌ **No Supported Links Found!**\n\n"
            "Supported sources:\n"
            "• Google Drive\n"
            "• Terabox\n"
            "• Direct download links"
        )
    
    # Check max size limit
    max_size, max_size_mb = await user_db.get_max_size(user_id)
    is_premium = await user_db.is_premium(user_id)
    
    # Create tasks
    tasks = []
    for link in supported_links:
        task = Task(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            url=link,
            chat_id=chat_id,
            topic_id=topic_id,
            reply_to_id=message.id
        )
        tasks.append(task)
    
    # Add tasks to queue
    added = await queue_manager.add_multiple_tasks(tasks)
    
    if added == 0:
        return await message.reply_text("❌ Failed to add tasks to queue!")
    
    # Increment usage for freemium users
    if not is_premium:
        for _ in range(min(added, remaining)):
            await user_db.increment_usage(user_id)
    
    # Send confirmation
    status_msg = await message.reply_text(
        f"📥 **{added} Task(s) Added to Queue!**\n\n"
        f"📊 Position: {queue_manager.get_queue_position(user_id)[0]}/{queue_manager.get_queue_position(user_id)[1]}\n"
        f"⏳ Processing will start shortly...",
        reply_to_message_id=message.id
    )
    
    # Try to pin message in group
    if is_group:
        try:
            await status_msg.pin(disable_notification=True)
        except:
            pass
    
    # Start processing if not already running
    if not queue_manager.is_processing(user_id):
        asyncio.create_task(process_queue(client, user_id, status_msg))

async def process_queue(client: Client, user_id: int, status_message: Message):
    """Process user's download queue"""
    queue_manager.set_processing(user_id, True)
    
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'file_types': {}
    }
    
    try:
        while True:
            # Check if cancelled
            if queue_manager.is_cancelled(user_id):
                queue_manager.clear_cancelled(user_id)
                break
            
            # Get next task
            task = await queue_manager.get_next_task(user_id)
            if not task:
                break
            
            results['total'] += 1
            current_pos, total_pos = queue_manager.get_queue_position(user_id)
            
            # Update status
            try:
                await status_message.edit_text(
                    f"📥 **Processing Tasks**\n\n"
                    f"📊 Progress: {current_pos}/{total_pos}\n"
                    f"🔗 Current: `{task.url[:50]}...`\n"
                    f"⏳ Please wait..."
                )
            except:
                pass
            
            # Process task
            success, file_type = await process_single_task(client, task, status_message)
            
            if success:
                results['success'] += 1
                if file_type:
                    results['file_types'][file_type] = results['file_types'].get(file_type, 0) + 1
                queue_manager.mark_completed(user_id, task.task_id, True)
            else:
                results['failed'] += 1
                queue_manager.mark_completed(user_id, task.task_id, False)
        
        # Send summary
        summary = generate_summary(results)
        
        try:
            await status_message.edit_text(summary)
            
            # Unpin in group
            if status_message.chat.type != "private":
                try:
                    await status_message.unpin()
                except:
                    pass
        except:
            pass
    
    except Exception as e:
        logger.error(f"Queue processing error: {e}")
        try:
            await status_message.edit_text(f"❌ Error: {str(e)}")
        except:
            pass
    
    finally:
        queue_manager.set_processing(user_id, False)
        queue_manager.clear_user_tasks(user_id)

async def process_single_task(client: Client, task: Task, progress_message: Message) -> tuple:
    """Process a single download task"""
    user_id = task.user_id
    url = task.url
    download_path = create_download_dir(user_id)
    
    try:
        # Determine link type and download
        task.status = "downloading"
        
        if is_gdrive_link(url):
            success, file_path, error = await downloader.download_gdrive(url, download_path, progress_message)
        elif is_terabox_link(url):
            success, file_path, error = await downloader.download_terabox(url, download_path, progress_message)
        else:
            success, file_path, error = await downloader.download_direct(url, download_path, progress_message)
        
        if not success:
            await progress_message.edit_text(f"❌ Download failed: {error}")
            await uploader.send_log(client, user_id, task.user_id, url, "Unknown", "failed", error)
            return False, None
        
        # Get file info
        filename = os.path.basename(file_path)
        extension = get_file_extension(filename)
        file_type = get_file_type(extension)
        task.filename = filename
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size, max_size_mb = await user_db.get_max_size(user_id)
        
        if file_size > max_size:
            await cleanup_file(file_path)
            error_msg = f"File too large! Max: {max_size_mb}MB"
            await progress_message.edit_text(f"❌ {error_msg}")
            await uploader.send_log(client, user_id, None, url, filename, "failed", error_msg)
            return False, None
        
        # Get user settings
        settings = await user_db.get_settings(user_id)
        custom_thumbnail = settings.get("thumbnail")
        custom_title = settings.get("title")
        target_chat = settings.get("chat_id") or task.chat_id
        
        # Format caption
        if custom_title:
            caption = custom_title.format(
                filename=filename,
                ext=extension,
                size=get_readable_file_size(file_size)
            )
        else:
            caption = f"📁 **{filename}**"
        
        # Upload file
        task.status = "uploading"
        
        success, sent_message, error = await uploader.upload_file(
            client,
            file_path,
            target_chat,
            progress_message,
            caption=caption,
            reply_to_message_id=task.reply_to_id if target_chat == task.chat_id else None,
            message_thread_id=task.topic_id,
            custom_thumbnail=custom_thumbnail
        )
        
        # Cleanup
        await cleanup_file(file_path)
        
        if success:
            await progress_message.edit_text(f"✅ **Uploaded Successfully!**\n\n📁 `{filename}`")
            
            # Get username for log
            try:
                user = await client.get_users(user_id)
                username = user.username
            except:
                username = None
            
            await uploader.send_log(client, user_id, username, url, filename, "success")
            return True, file_type
        else:
            await progress_message.edit_text(f"❌ Upload failed: {error}")
            await uploader.send_log(client, user_id, None, url, filename, "failed", error)
            return False, None
    
    except asyncio.CancelledError:
        await cleanup_file(download_path)
        return False, None
    
    except Exception as e:
        logger.error(f"Task processing error: {e}")
        await cleanup_file(download_path)
        try:
            await progress_message.edit_text(f"❌ Error: {str(e)}")
        except:
            pass
        return False, None

# Import for InlineKeyboardMarkup
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import get_readable_file_size
