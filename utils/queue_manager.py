import asyncio
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class Task:
    task_id: str
    user_id: int
    url: str
    filename: str = "Unknown"
    status: str = "queued"  # queued, downloading, uploading, completed, failed, cancelled
    progress: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    topic_id: Optional[int] = None
    reply_to_id: Optional[int] = None

class QueueManager:
    def __init__(self):
        self.queues: Dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.active_tasks: Dict[int, Task] = {}
        self.user_tasks: Dict[int, List[Task]] = defaultdict(list)
        self.cancelled_users: set = set()
        self.processing: Dict[int, bool] = defaultdict(bool)
        self.locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def add_task(self, task: Task) -> bool:
        """Add task to user's queue"""
        try:
            self.user_tasks[task.user_id].append(task)
            await self.queues[task.user_id].put(task)
            logger.info(f"Task added: {task.task_id} for user {task.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            return False
    
    async def add_multiple_tasks(self, tasks: List[Task]) -> int:
        """Add multiple tasks to queue"""
        count = 0
        for task in tasks:
            if await self.add_task(task):
                count += 1
        return count
    
    async def get_next_task(self, user_id: int) -> Optional[Task]:
        """Get next task from user's queue"""
        try:
            if self.queues[user_id].empty():
                return None
            
            task = await self.queues[user_id].get()
            self.active_tasks[user_id] = task
            return task
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return None
    
    def set_current_task(self, user_id: int, task: Task):
        """Set current active task for user"""
        self.active_tasks[user_id] = task
    
    def get_current_task(self, user_id: int) -> Optional[Task]:
        """Get current active task for user"""
        return self.active_tasks.get(user_id)
    
    def get_user_tasks(self, user_id: int) -> List[Task]:
        """Get all tasks for user"""
        return [t for t in self.user_tasks[user_id] if t.status in ["queued", "downloading", "uploading"]]
    
    def get_queue_size(self, user_id: int) -> int:
        """Get queue size for user"""
        return self.queues[user_id].qsize()
    
    def get_total_tasks(self, user_id: int) -> int:
        """Get total pending tasks for user"""
        return len(self.get_user_tasks(user_id))
    
    def get_queue_position(self, user_id: int) -> tuple:
        """Get current position and total in queue"""
        tasks = self.user_tasks[user_id]
        completed = sum(1 for t in tasks if t.status in ["completed", "failed", "cancelled"])
        total = len(tasks)
        return completed + 1, total
    
    async def cancel_current_task(self, user_id: int) -> bool:
        """Cancel current running task"""
        if user_id in self.active_tasks:
            self.active_tasks[user_id].status = "cancelled"
            self.cancelled_users.add(user_id)
            return True
        return False
    
    async def cancel_all_tasks(self, user_id: int) -> int:
        """Cancel all tasks for user"""
        self.cancelled_users.add(user_id)
        
        count = 0
        # Cancel active task
        if user_id in self.active_tasks:
            self.active_tasks[user_id].status = "cancelled"
            count += 1
        
        # Cancel queued tasks
        while not self.queues[user_id].empty():
            try:
                task = self.queues[user_id].get_nowait()
                task.status = "cancelled"
                count += 1
            except:
                break
        
        # Mark all user tasks as cancelled
        for task in self.user_tasks[user_id]:
            if task.status in ["queued", "downloading", "uploading"]:
                task.status = "cancelled"
        
        return count
    
    def is_cancelled(self, user_id: int) -> bool:
        """Check if user's tasks are cancelled"""
        return user_id in self.cancelled_users
    
    def clear_cancelled(self, user_id: int):
        """Clear cancelled status for user"""
        self.cancelled_users.discard(user_id)
    
    def mark_completed(self, user_id: int, task_id: str, success: bool = True):
        """Mark task as completed"""
        for task in self.user_tasks[user_id]:
            if task.task_id == task_id:
                task.status = "completed" if success else "failed"
                break
        
        if user_id in self.active_tasks and self.active_tasks[user_id].task_id == task_id:
            del self.active_tasks[user_id]
    
    def clear_user_tasks(self, user_id: int):
        """Clear all tasks for user"""
        self.user_tasks[user_id].clear()
        self.cancelled_users.discard(user_id)
        
        # Clear queue
        while not self.queues[user_id].empty():
            try:
                self.queues[user_id].get_nowait()
            except:
                break
        
        if user_id in self.active_tasks:
            del self.active_tasks[user_id]
    
    def is_processing(self, user_id: int) -> bool:
        """Check if user's queue is being processed"""
        return self.processing.get(user_id, False)
    
    def set_processing(self, user_id: int, status: bool):
        """Set processing status for user"""
        self.processing[user_id] = status
    
    def get_stats(self, user_id: int) -> dict:
        """Get task statistics for user"""
        tasks = self.user_tasks[user_id]
        
        return {
            'total': len(tasks),
            'completed': sum(1 for t in tasks if t.status == "completed"),
            'failed': sum(1 for t in tasks if t.status == "failed"),
            'cancelled': sum(1 for t in tasks if t.status == "cancelled"),
            'pending': sum(1 for t in tasks if t.status in ["queued", "downloading", "uploading"])
        }

# Global queue manager instance
queue_manager = QueueManager()
