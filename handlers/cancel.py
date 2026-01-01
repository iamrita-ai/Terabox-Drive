import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.queue_manager import queue_manager

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("cancel"))
async def cancel_command(client: Client, message: Message):
    """Handle /cancel command"""
    user_id = message.from_user.id
    
    # Check if user has active tasks
    active_tasks = queue_manager.get_user_tasks(user_id)
    
    if not active_tasks:
        return await message.reply_text(
            "❌ **No Active Tasks!**\n\n"
            "You don't have any running tasks to cancel."
        )
    
    # Show cancel options
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Cancel Current Task", callback_data=f"cancel_current_{user_id}")],
        [InlineKeyboardButton("🚫 Cancel All Tasks", callback_data=f"cancel_all_{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    tasks_text = "\n".join([f"• {task['filename']}" for task in active_tasks[:5]])
    if len(active_tasks) > 5:
        tasks_text += f"\n... and {len(active_tasks) - 5} more"
    
    await message.reply_text(
        f"⚠️ **Active Tasks ({len(active_tasks)})**\n\n"
        f"{tasks_text}\n\n"
        f"What do you want to cancel?",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex("^cancel_current_"))
async def cancel_current_callback(client: Client, callback_query: CallbackQuery):
    """Cancel current task callback"""
    user_id = int(callback_query.data.split("_")[2])
    
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("❌ Not your task!", show_alert=True)
    
    success = await queue_manager.cancel_current_task(user_id)
    
    if success:
        await callback_query.message.edit_text(
            "✅ **Current task cancelled!**\n\n"
            "The running task has been stopped."
        )
        await callback_query.answer("Task cancelled!", show_alert=True)
    else:
        await callback_query.answer("❌ No task to cancel!", show_alert=True)

@Client.on_callback_query(filters.regex("^cancel_all_"))
async def cancel_all_callback(client: Client, callback_query: CallbackQuery):
    """Cancel all tasks callback"""
    user_id = int(callback_query.data.split("_")[2])
    
    if callback_query.from_user.id != user_id:
        return await callback_query.answer("❌ Not your tasks!", show_alert=True)
    
    count = await queue_manager.cancel_all_tasks(user_id)
    
    await callback_query.message.edit_text(
        f"✅ **All tasks cancelled!**\n\n"
        f"Cancelled {count} task(s)."
    )
    await callback_query.answer(f"Cancelled {count} tasks!", show_alert=True)
