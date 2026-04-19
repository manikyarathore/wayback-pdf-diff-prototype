"""
Utility functions and helpers for the PDF diff pipeline.
"""

import logging
import time
import json
from pathlib import Path
from typing import Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class Timer:
    """Context manager for timing code blocks."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start = None
        self.elapsed = 0.0
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed = (time.time() - self.start) * 1000  # Convert to ms
        logger.debug(f"{self.name}: {self.elapsed:.1f}ms")


def timer_decorator(func: Callable) -> Callable:
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            logger.debug(f"{func_name}: {elapsed:.1f}ms")
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"{func_name} failed after {elapsed:.1f}ms: {e}")
            raise
    
    return wrapper


def safe_file_read(file_path: str) -> str:
    """Safely read file with error handling."""
    try:
        return Path(file_path).read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        raise


def safe_file_write(file_path: str, content: str) -> bool:
    """Safely write file with error handling."""
    try:
        Path(file_path).write_text(content, encoding='utf-8')
        logger.info(f"Wrote {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write {file_path}: {e}")
        return False


def format_file_size(bytes_: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_ < 1024:
            return f"{bytes_:.1f}{unit}"
        bytes_ /= 1024
    return f"{bytes_:.1f}TB"


def format_duration(milliseconds: float) -> str:
    """Format milliseconds as human-readable duration."""
    if milliseconds < 1000:
        return f"{milliseconds:.1f}ms"
    elif milliseconds < 60000:
        return f"{milliseconds / 1000:.1f}s"
    else:
        minutes = milliseconds / 60000
        return f"{minutes:.1f}min"


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for non-standard types."""
    
    def default(self, obj: Any) -> Any:
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if hasattr(obj, '__dataclass_fields__'):
            return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
        return super().default(obj)


def safe_json_dump(obj: Any, file_path: str = None, indent: int = 2) -> str:
    """Safely serialize object to JSON."""
    try:
        json_str = json.dumps(obj, cls=JSONEncoder, indent=indent, default=str)
        if file_path:
            Path(file_path).write_text(json_str)
            logger.info(f"Wrote JSON: {file_path}")
        return json_str
    except Exception as e:
        logger.error(f"JSON serialization failed: {e}")
        raise


def batch_process(items: list, batch_size: int = 10):
    """Generator to process items in batches."""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def deduplicate_preserving_order(items: list) -> list:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class ProgressTracker:
    """Simple progress tracker with logging."""
    
    def __init__(self, total: int, name: str = "Processing"):
        self.total = total
        self.name = name
        self.current = 0
        self.start_time = time.time()
    
    def update(self, increment: int = 1):
        """Update progress."""
        self.current += increment
        percent = (self.current / self.total * 100) if self.total > 0 else 0
        elapsed = time.time() - self.start_time
        
        if self.current > 0:
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate if rate > 0 else 0
            logger.info(
                f"{self.name}: {self.current}/{self.total} ({percent:.1f}%) "
                f"- ETA: {remaining:.0f}s"
            )
    
    def finish(self):
        """Mark as finished."""
        elapsed = time.time() - self.start_time
        logger.info(f"{self.name}: Complete in {format_duration(elapsed * 1000)}")


def validate_pdf_path(path: str) -> bool:
    """Validate that path points to a valid PDF."""
    try:
        p = Path(path)
        if not p.exists():
            logger.error(f"File does not exist: {path}")
            return False
        if p.suffix.lower() != '.pdf':
            logger.error(f"Not a PDF file: {path}")
            return False
        if not p.is_file():
            logger.error(f"Not a file: {path}")
            return False
        return True
    except Exception as e:
        logger.error(f"Path validation failed: {e}")
        return False


def merge_dicts(*dicts) -> dict:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def filter_by_key(items: list, key_func: Callable, value: Any) -> list:
    """Filter items by key function."""
    return [item for item in items if key_func(item) == value]


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def get_memory_usage() -> str:
    """Get current memory usage (requires psutil)."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return format_file_size(memory_info.rss)
    except ImportError:
        return "N/A (install psutil)"


class CachedProperty:
    """Decorator for cached property computation."""
    
    def __init__(self, func):
        self.func = func
        self.result = None
        self.computed = False
    
    def __get__(self, obj, type=None):
        if not self.computed:
            self.result = self.func(obj)
            self.computed = True
        return self.result


def create_report(data: dict, format_type: str = 'json') -> str:
    """Create formatted report from data."""
    if format_type == 'json':
        return safe_json_dump(data)
    elif format_type == 'text':
        return '\n'.join(f"{k}: {v}" for k, v in data.items())
    else:
        return str(data)


def validate_confidence_score(score: float) -> bool:
    """Validate confidence score is in range [0, 100]."""
    return 0.0 <= score <= 100.0


def normalize_score(value: float, min_val: float = 0, max_val: float = 1) -> float:
    """Normalize value to range [0, 1]."""
    if max_val == min_val:
        return 0.0
    return (value - min_val) / (max_val - min_val)


def denormalize_score(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Denormalize value from [0, 1] to [min, max]."""
    return value * (max_val - min_val) + min_val


# Logging utilities

def setup_logging(level: str = "INFO", log_file: str = None):
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(format_str))
    
    # File handler (if specified)
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(format_str))
        handlers.append(file_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in handlers:
        root_logger.addHandler(handler)


def log_dict(data: dict, level: int = logging.DEBUG):
    """Log dictionary in formatted way."""
    logger.log(level, "Data: " + json.dumps(data, indent=2, default=str))
