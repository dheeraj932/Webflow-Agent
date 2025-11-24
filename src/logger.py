"""
Simple logging utility for the agent system
"""

import sys
from enum import Enum


class LogLevel(Enum):
    """Log levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


class Logger:
    """Simple logger for console output"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
    
    def _log(self, level: LogLevel, message: str, emoji: str = ""):
        """Internal logging method"""
        if not self.verbose and level == LogLevel.DEBUG:
            return
        
        prefix = f"{emoji} " if emoji else ""
        print(f"{prefix}{message}", file=sys.stdout if level != LogLevel.ERROR else sys.stderr)
    
    def info(self, message: str, emoji: str = "ℹ️"):
        """Log info message"""
        self._log(LogLevel.INFO, message, emoji)
    
    def success(self, message: str):
        """Log success message"""
        self._log(LogLevel.INFO, message, "✅")
    
    def warning(self, message: str):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, "⚠️")
    
    def error(self, message: str):
        """Log error message"""
        self._log(LogLevel.ERROR, message, "❌")
    
    def debug(self, message: str):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, "🔍")


# Global logger instance
logger = Logger()

