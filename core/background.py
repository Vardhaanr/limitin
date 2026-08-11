import threading
import queue
import time
from typing import Callable, Any, Optional
from services.logger import get_logger


class BackgroundTask:
    """Represents a background task."""
    
    def __init__(self, func: Callable, args: tuple = (), kwargs: dict = None, 
                 callback: Optional[Callable] = None):
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.callback = callback
        self.result = None
        self.error = None
        self.completed = False


class BackgroundService:
    """Manages background tasks with thread pool."""
    
    def __init__(self, num_workers: int = 4):
        self.logger = get_logger()
        self.num_workers = num_workers
        self.task_queue: queue.Queue[BackgroundTask] = queue.Queue()
        self.workers: list[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()
    
    def start(self):
        """Start the background service."""
        if self.running:
            return
        
        self.running = True
        self.logger.info(f"Starting background service with {self.num_workers} workers")
        
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """Stop the background service."""
        if not self.running:
            return
        
        self.logger.info("Stopping background service")
        self.running = False
        
        # Add sentinel values to wake up workers
        for _ in range(self.num_workers):
            self.task_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
    
    def submit(self, func: Callable, args: tuple = (), kwargs: dict = None,
               callback: Optional[Callable] = None) -> BackgroundTask:
        """Submit a task to be executed in the background."""
        task = BackgroundTask(func, args, kwargs, callback)
        self.task_queue.put(task)
        return task
    
    def _worker_loop(self):
        """Worker thread loop."""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                
                # Sentinel value to stop
                if task is None:
                    break
                
                self._execute_task(task)
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker error: {e}", exc_info=True)
    
    def _execute_task(self, task: BackgroundTask):
        """Execute a single task."""
        try:
            self.logger.debug(f"Executing task: {task.func.__name__}")
            task.result = task.func(*task.args, **task.kwargs)
            task.completed = True
            
            if task.callback:
                self._safe_callback(task.callback, task.result, None)
                
        except Exception as e:
            task.error = e
            self.logger.error(f"Task failed: {e}", exc_info=True)
            
            if task.callback:
                self._safe_callback(task.callback, None, e)
    
    def _safe_callback(self, callback: Callable, result: Any, error: Optional[Exception]):
        """Safely execute a callback (typically on main thread)."""
        try:
            callback(result, error)
        except Exception as e:
            self.logger.error(f"Callback error: {e}", exc_info=True)


class UIUpdateScheduler:
    """Schedules UI updates from background threads safely."""
    
    def __init__(self):
        self.logger = get_logger()
        self.update_queue: queue.Queue[Callable] = queue.Queue()
        self.running = False
        self._scheduler_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the UI update scheduler."""
        if self.running:
            return
        
        self.running = True
        self.logger.info("Starting UI update scheduler")
        
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="UIUpdateScheduler",
            daemon=True
        )
        self._scheduler_thread.start()
    
    def stop(self):
        """Stop the UI update scheduler."""
        if not self.running:
            return
        
        self.logger.info("Stopping UI update scheduler")
        self.running = False
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)
    
    def schedule(self, callback: Callable):
        """Schedule a UI update callback."""
        self.update_queue.put(callback)
    
    def _scheduler_loop(self):
        """Scheduler loop (meant to be polled from main thread)."""
        while self.running:
            try:
                callback = self.update_queue.get(timeout=0.1)
                callback()
                self.update_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"UI update error: {e}", exc_info=True)
    
    def process_updates(self):
        """Process pending updates (call from main thread)."""
        while not self.update_queue.empty():
            try:
                callback = self.update_queue.get_nowait()
                callback()
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"UI update error: {e}", exc_info=True)


# Global instances
_background_service: Optional[BackgroundService] = None
_ui_scheduler: Optional[UIUpdateScheduler] = None


def get_background_service() -> BackgroundService:
    """Get the global background service instance."""
    global _background_service
    if _background_service is None:
        _background_service = BackgroundService()
    return _background_service


def get_ui_scheduler() -> UIUpdateScheduler:
    """Get the global UI scheduler instance."""
    global _ui_scheduler
    if _ui_scheduler is None:
        _ui_scheduler = UIUpdateScheduler()
    return _ui_scheduler


def start_background_services():
    """Start all background services."""
    get_background_service().start()
    get_ui_scheduler().start()


def stop_background_services():
    """Stop all background services."""
    get_background_service().stop()
    get_ui_scheduler().stop()


def reset_background_services():
    """Reset global instances (for testing)."""
    global _background_service, _ui_scheduler
    if _background_service:
        _background_service.stop()
    if _ui_scheduler:
        _ui_scheduler.stop()
    _background_service = None
    _ui_scheduler = None
