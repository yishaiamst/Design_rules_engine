#!/usr/bin/env python3
"""
Timeout and timing utilities for debug scripts
"""

import signal
import time
import sys
from contextlib import contextmanager
from functools import wraps


class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Operation timed out")


@contextmanager
def timeout(seconds):
    """Context manager for timeout operations"""
    if hasattr(signal, 'SIGALRM'):
        # Unix-like systems
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows/Mac - use a different approach
        start_time = time.time()
        yield
        elapsed = time.time() - start_time
        if elapsed > seconds:
            raise TimeoutError(f"Operation took {elapsed:.1f}s, exceeded {seconds}s timeout")


def timer(func):
    """Decorator to time function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            print(f"  ⏱️  {func.__name__} took {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ⏱️  {func.__name__} failed after {elapsed:.2f}s: {e}")
            raise
    return wrapper


class Timer:
    """Simple timer context manager"""
    def __init__(self, description="Operation"):
        self.description = description
        self.start_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed = time.time() - self.start_time
        print(f"  ⏱️  {self.description}: {self.elapsed:.2f}s")
    
    def elapsed_time(self):
        """Get elapsed time"""
        if self.start_time:
            return time.time() - self.start_time
        return self.elapsed if self.elapsed else 0

