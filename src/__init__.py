"""
UI State Capture Agent System

An AI-powered multi-agent system that automatically navigates web applications
and captures UI states based on natural language instructions.

Agent B receives natural language questions and automatically:
- Navigates the live web application
- Performs the requested task
- Captures screenshots of each UI state in the workflow
- Organizes the captured states by task
"""

__version__ = "1.0.0"

from .agent import AgentB
from .navigator import Navigator
from .screenshot import ScreenshotCapture

__all__ = ["AgentB", "Navigator", "ScreenshotCapture"]

