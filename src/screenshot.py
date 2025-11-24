"""
ScreenshotCapture - Handles capturing UI states as screenshots
"""

import os
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page


class ScreenshotCapture:
    """Handles screenshot capture of UI states"""
    
    def __init__(self):
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.counter = 0
        self.last_screenshot_path = None  # Track last screenshot for duplicate detection
    
    def _should_skip_capture(self, description: str, capture_type: str) -> bool:
        """
        Determine if a screenshot should be skipped based on description.
        Skips discovery/find/wait steps that don't change UI state.
        
        Args:
            description: Description of the state
            capture_type: Type of capture (before, after, final)
            
        Returns:
            True if screenshot should be skipped, False otherwise
        """
        description_lower = description.lower()
        
        # Always capture final states
        if capture_type == "final" or "final" in description_lower:
            return False
        
        # Always capture login states
        if "login" in description_lower or capture_type == "after-login":
            return False
        
        # Skip discovery/find/wait steps - they don't change UI state
        skip_keywords = [
            "discover", "find", "extract", "identify", "locate", 
            "search", "wait", "check", "verify", "read", "examine"
        ]
        
        # Check if description contains skip keywords
        if any(keyword in description_lower for keyword in skip_keywords):
            # But allow if it's a meaningful action (e.g., "find and click" is different from just "find")
            meaningful_actions = ["click", "type", "select", "submit", "navigate"]
            if not any(action in description_lower for action in meaningful_actions):
                return True
        
        return False
    
    async def capture(self, page: Page, description: str, capture_type: str = "state") -> dict:
        """
        Capture a screenshot of the current UI state
        
        Args:
            page: Playwright page object
            description: Description of the state
            capture_type: Type of capture (before, after, final)
            
        Returns:
            Screenshot metadata dictionary or None if skipped
        """
        # Check if we should skip this capture
        if self._should_skip_capture(description, capture_type):
            print(f"  ⏭️  Skipped: {description} ({capture_type}) - no UI state change")
            return None
        
        self.counter += 1
        
        # Create filename
        timestamp = int(datetime.now().timestamp() * 1000)
        sanitized_description = re.sub(
            r'[^a-z0-9]+', '-',
            description.lower()
        ).strip('-')[:50]
        
        filename = f"{self.counter}-{capture_type}-{sanitized_description}-{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        # Capture screenshot
        await page.screenshot(
            path=str(filepath),
            full_page=True,  # Capture full page, not just viewport
            animations="disabled"  # Disable animations for consistent captures
        )
        
        print(f"  📸 Captured: {description} ({capture_type})")
        
        # Update last screenshot path
        self.last_screenshot_path = str(filepath)
        
        return {
            "path": str(filepath),
            "name": f"{capture_type}-{sanitized_description}",
            "description": description,
            "type": capture_type,
            "timestamp": datetime.now().isoformat(),
            "counter": self.counter
        }
    
    async def capture_element(self, page: Page, selector: str, description: str) -> dict:
        """
        Capture a specific element (e.g., modal, form)
        
        Args:
            page: Playwright page object
            selector: CSS selector for the element
            description: Description of what's being captured
            
        Returns:
            Screenshot metadata dictionary
        """
        self.counter += 1
        
        timestamp = int(datetime.now().timestamp() * 1000)
        sanitized_description = re.sub(
            r'[^a-z0-9]+', '-',
            description.lower()
        ).strip('-')[:50]
        
        filename = f"element-{self.counter}-{sanitized_description}-{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            element = page.locator(selector).first
            await element.screenshot(path=str(filepath))
            
            print(f"  📸 Captured element: {description}")
            
            return {
                "path": str(filepath),
                "name": f"element-{sanitized_description}",
                "description": description,
                "type": "element",
                "timestamp": datetime.now().isoformat(),
                "counter": self.counter
            }
        except Exception as e:
            print(f"  ⚠️  Could not capture element {selector}: {e}")
            # Fallback to full page screenshot
            return await self.capture(page, description, "element-fallback")
    
    def reset(self):
        """Reset counter (useful for new tasks)"""
        self.counter = 0
        self.last_screenshot_path = None

