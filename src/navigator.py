"""
Navigator - Handles web navigation and UI interactions
Uses Playwright with Chrome browser
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import os
import re


class Navigator:
    """Handles browser navigation and UI interactions"""
    
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
    
    async def initialize(self):
        """Initialize browser with Chrome - configured to avoid detection"""
        print("🌐 Launching Chrome browser...")
        
        self.playwright = await async_playwright().start()
        
        # Use Chrome instead of Chromium with stealth settings
        self.browser = await self.playwright.chromium.launch(
            channel="chrome",  # Use Chrome instead of Chromium
            headless=os.getenv("HEADLESS", "false").lower() != "false",
            slow_mo=int(os.getenv("SLOW_MO", "100")),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )
        
        # Create context with realistic browser fingerprint
        # Use persistent storage to maintain login state
        storage_path = os.getenv("BROWSER_STORAGE_PATH", "browser_storage")
        os.makedirs(storage_path, exist_ok=True)
        state_file = os.path.join(storage_path, "state.json")
        
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/Los_Angeles",
            permissions=["geolocation"],
            storage_state=state_file if os.path.exists(state_file) else None,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            }
        )
        
        self.page = await self.context.new_page()
        
        # Inject JavaScript to hide automation indicators
        await self.page.add_init_script("""
            // Override the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override the plugins property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override the languages property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override the chrome property
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        print("✅ Browser initialized with stealth settings")
    
    async def navigate(self, url: str):
        """Navigate to a URL"""
        print(f"  → Navigating to: {url}")
        await self.page.goto(url, wait_until="networkidle")
        await asyncio.sleep(1)  # Wait for dynamic content
    
    async def click(self, selector: str):
        """Click on an element - supports multiple selector strategies"""
        print(f"  → Clicking: {selector}")
        
        # Detect selector type and extract the actual value
        is_aria_label_selector = selector.startswith("aria-label=") or selector.startswith("[aria-label")
        is_text_selector = selector.startswith("text=")
        
        # Clean selector - extract the actual value
        if is_aria_label_selector:
            # Extract value from aria-label selector (e.g., "aria-label=Submit" -> "Submit")
            if "=" in selector:
                clean_selector = selector.split("=", 1)[1].strip("'\"")
            elif "[" in selector and "]" in selector:
                # Handle [aria-label="value"] format
                match = re.search(r'aria-label[=:]\s*["\']?([^"\']+)["\']?', selector)
                clean_selector = match.group(1) if match else selector
            else:
                clean_selector = selector.replace("aria-label", "").strip("=: '\"")
        elif is_text_selector:
            clean_selector = selector.replace("text=", "").strip("'\"")
        else:
            clean_selector = selector.strip("'\"")
        
        clean_selector_lower = clean_selector.lower()
        
        # Detect ambiguous selectors that might match multiple buttons
        ambiguous_keywords = ["create", "new", "add", "edit", "delete", "save", "submit"]
        is_ambiguous = (
            len(clean_selector.split()) == 1 and  # Single word
            any(keyword in clean_selector_lower for keyword in ambiguous_keywords)
        ) or is_aria_label_selector  # Always use intelligent comparison for aria-label selectors
        
        # If ambiguous or aria-label selector, skip to Strategy 5 (intelligent comparison) immediately
        if is_ambiguous or is_aria_label_selector:
            print(f"  🔍 Using intelligent comparison for selector: {clean_selector}")
            # Skip strategies 1-4 and go straight to Strategy 5
        else:
            # Try simpler strategies first for non-ambiguous selectors
            try:
                # Strategy 1: Try direct selector first (if it's a CSS selector)
                await self.page.click(selector, timeout=5000)
                await asyncio.sleep(0.5)
                return
            except Exception:
                pass
                
            # Strategy 2: Try exact text match
            try:
                await self.page.click(f"text={clean_selector}", timeout=5000)
                await asyncio.sleep(0.5)
                return
            except Exception:
                pass
        
        # Strategy 5: Find all buttons/clickable elements and match by text content and aria-label
        # This strategy scores buttons to find the best match when multiple buttons match
        # ALWAYS use this for ambiguous selectors, aria-label selectors, or when simpler strategies fail
        try:
            # Get all buttons and clickable elements
            buttons = await self.page.query_selector_all(
                'button, [role="button"], a[href], [onclick], [class*="Button"], [class*="button"]'
            )
            
            scored_buttons = []
            
            for btn in buttons:
                try:
                    if not await btn.is_visible():
                        continue
                    
                    # Check if it's actually an input element (checkbox/toggle) - skip these entirely
                    tag_name = await btn.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == "input":
                        input_type = await btn.get_attribute("type") or ""
                        # Skip checkbox/toggle inputs - they're not clickable buttons for actions
                        if input_type in ["checkbox", "radio"]:
                            continue
                    
                    # Get text content
                    text_content = (await btn.text_content() or "").strip()
                    text_lower = text_content.lower()
                    
                    # Get aria-label as fallback
                    aria_label = await btn.get_attribute("aria-label") or ""
                    aria_label = aria_label.strip() if aria_label else ""
                    aria_lower = aria_label.lower()
                    
                    # Get button type and attributes
                    btn_type = await btn.get_attribute("type") or ""
                    btn_id = await btn.get_attribute("id") or ""
                    btn_class = await btn.get_attribute("class") or ""
                    
                    # CRITICAL: Skip "Create more" and similar toggle buttons entirely
                    text_has_more = "more" in text_lower and len(text_lower.split()) <= 3
                    aria_has_more = "more" in aria_lower and len(aria_lower.split()) <= 3
                    id_has_toggle = "toggle" in btn_id.lower() or "more" in btn_id.lower()
                    
                    # Also check if it's a checkbox input with "more" in the context
                    is_checkbox_with_more = (
                        tag_name == "input" and 
                        (input_type == "checkbox" or "toggle" in btn_id.lower() or "more" in btn_id.lower())
                    )
                    
                    if text_has_more or aria_has_more or id_has_toggle or is_checkbox_with_more:
                        # This is a toggle/settings button, skip it entirely
                        print(f"  🚫 Skipping toggle button: '{text_content}' (id: {btn_id})")
                        continue
                    
                    # Score the match (higher is better)
                    score = 0
                    matched = False
                    
                    # If this is an aria-label selector, prioritize aria-label matching
                    if is_aria_label_selector:
                        # Exact aria-label match gets highest score
                        if clean_selector_lower == aria_lower:
                            score += 100
                            matched = True
                        # Aria-label starts with selector (e.g., "Create issue" matches "Create new issue")
                        elif aria_lower.startswith(clean_selector_lower):
                            score += 80
                            matched = True
                        # Selector starts with aria-label (e.g., "Create new issue" matches "Create issue")
                        elif clean_selector_lower.startswith(aria_lower):
                            score += 75
                            matched = True
                        # Bidirectional partial match - check if they share significant words
                        elif self._share_significant_words(clean_selector_lower, aria_lower):
                            score += 60
                            matched = True
                        # Partial match (contains)
                        elif clean_selector_lower in aria_lower or aria_lower in clean_selector_lower:
                            score += 40
                            matched = True
                    else:
                        # Text-based matching (existing logic)
                        # Exact match gets highest score
                        if clean_selector_lower == text_lower or clean_selector_lower == aria_lower:
                            score += 100
                            matched = True
                        # Text starts with selector followed by space
                        elif text_lower.startswith(clean_selector_lower + " "):
                            score += 80
                            matched = True
                        # Selector is at the start of text
                        elif text_lower.startswith(clean_selector_lower):
                            score += 60
                            matched = True
                        # Bidirectional partial match
                        elif self._share_significant_words(clean_selector_lower, text_lower) or self._share_significant_words(clean_selector_lower, aria_lower):
                            score += 50
                            matched = True
                        # Partial match (contains)
                        elif clean_selector_lower in text_lower or clean_selector_lower in aria_lower:
                            score += 40
                            matched = True
                    
                    if not matched:
                        continue
                    
                    # Check if button is in a form/modal context (submit buttons usually are)
                    try:
                        in_form_context = await btn.evaluate("""
                            (el) => {
                                let current = el;
                                while (current && current.parentElement) {
                                    current = current.parentElement;
                                    if (current.tagName === 'FORM' || 
                                        current.getAttribute('role') === 'dialog' ||
                                        current.classList.contains('modal') ||
                                        current.classList.contains('form') ||
                                        current.classList.contains('Dialog')) {
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """)
                        if in_form_context:
                            score += 30  # Big bonus for being in form/modal context
                    except Exception:
                        pass
                    
                    # Bonus points for submit/primary buttons
                    if btn_type == "submit":
                        score += 30
                    if "submit" in btn_class.lower() or "primary" in btn_class.lower():
                        score += 25
                    # Prefer buttons with full action descriptions (multi-word buttons)
                    word_count = len(text_lower.split()) if text_lower else len(aria_lower.split())
                    if word_count >= 2:
                        score += 20
                    
                    # Additional penalties for toggle/checkbox-like buttons
                    if "toggle" in btn_id.lower() or "toggle" in btn_class.lower():
                        score -= 100
                    if "checkbox" in btn_class.lower() or "switch" in btn_class.lower():
                        score -= 100
                    
                    scored_buttons.append({
                        "element": btn,
                        "score": score,
                        "text": text_content,
                        "aria_label": aria_label,
                        "id": btn_id
                    })
                except Exception:
                    continue
            
            # ALWAYS do semantic comparison when we have matches
            if scored_buttons:
                if len(scored_buttons) > 1:
                    print(f"  🔍 Found {len(scored_buttons)} matching buttons, comparing semantically...")
                    
                    # Explicit comparison for better matching
                    for candidate in scored_buttons:
                        text_lower = candidate["text"].lower()
                        aria_lower = candidate.get("aria_label", "").lower()
                        candidate_id = candidate.get("id", "").lower()
                        
                        # Check if this is "Create more" or similar toggle
                        is_toggle = (
                            "more" in text_lower or 
                            "more" in aria_lower or
                            "toggle" in candidate_id or
                            "more" in candidate_id
                        )
                        
                        # Check if this is a full action button using general patterns
                        word_count = len(text_lower.split()) if text_lower else len(aria_lower.split())
                        has_toggle_words = any(word in text_lower or word in aria_lower for word in ["more", "less", "toggle", "switch"])
                        is_action_button = (
                            word_count >= 2 and
                            not has_toggle_words and
                            not text_lower.endswith(" more") and
                            not aria_lower.endswith(" more") and
                            not text_lower.endswith(" less") and
                            not aria_lower.endswith(" less")
                        )
                        
                        if is_toggle:
                            candidate["score"] -= 200
                            print(f"     ⚠️  '{candidate['text'] or candidate.get('aria_label', '')}' identified as toggle/settings button (penalty: -200)")
                        
                        if is_action_button:
                            candidate["score"] += 100
                            print(f"     ✅ '{candidate['text'] or candidate.get('aria_label', '')}' identified as action button (bonus: +100)")
                        
                        # Additional bonus for buttons in form/modal context
                        try:
                            in_form = await candidate["element"].evaluate("""
                                (el) => {
                                    let current = el;
                                    while (current && current.parentElement) {
                                        current = current.parentElement;
                                        if (current.tagName === 'FORM' || 
                                            current.getAttribute('role') === 'dialog') {
                                            return true;
                                        }
                                    }
                                    return false;
                                }
                            """)
                            if in_form:
                                candidate["score"] += 50
                                print(f"     ✅ '{candidate['text'] or candidate.get('aria_label', '')}' is in form/modal context (bonus: +50)")
                        except Exception:
                            pass
                    
                    # Re-sort after all adjustments
                    scored_buttons.sort(key=lambda x: x["score"], reverse=True)
                    
                    # Show final comparison
                    print(f"  📊 Final button comparison:")
                    for i, btn_info in enumerate(scored_buttons[:3]):
                        marker = "👉 SELECTED" if i == 0 else ""
                        display_text = btn_info['text'] or btn_info.get('aria_label', '') or 'No text'
                        print(f"     {i+1}. '{display_text}' (final score: {btn_info['score']}) {marker}")
                
                # Final safety check: if best match is "Create more", try to find a better one
                best_match = scored_buttons[0]
                best_text_lower = (best_match["text"] or "").lower()
                best_aria_lower = (best_match.get("aria_label") or "").lower()
                
                if "more" in best_text_lower or "more" in best_aria_lower:
                    if len(scored_buttons) > 1:
                        for alt_match in scored_buttons[1:]:
                            alt_text_lower = (alt_match["text"] or "").lower()
                            alt_aria_lower = (alt_match.get("aria_label") or "").lower()
                            if "more" not in alt_text_lower and "more" not in alt_aria_lower:
                                print(f"  🔄 Overriding selection: '{best_match['text'] or best_match.get('aria_label', '')}' -> '{alt_match['text'] or alt_match.get('aria_label', '')}' (avoiding toggle)")
                                best_match = alt_match
                                break
                
                await best_match["element"].click()
                display_text = best_match['text'] or best_match.get('aria_label', '') or 'No text'
                print(f"  ✅ Clicked button: '{display_text}' (final score: {best_match['score']})")
                await asyncio.sleep(0.5)
                return
        except Exception:
            pass
        
        # Strategy 6: Try finding by data attributes or other selectors
        try:
            # Try various attribute-based selectors
            attribute_selectors = [
                f'[aria-label*="{clean_selector}"]',
                f'[data-testid*="{clean_selector.lower()}"]',
                f'[title*="{clean_selector}"]',
                f'button[aria-label*="{clean_selector}"]',
            ]
            
            for attr_selector in attribute_selectors:
                try:
                    element = await self.page.query_selector(attr_selector)
                    if element and await element.is_visible():
                        await element.click()
                        print(f"  ✅ Clicked element via attribute selector: {attr_selector}")
                        await asyncio.sleep(0.5)
                        return
                except Exception:
                    continue
        except Exception:
            pass
        
        # If all strategies fail, capture HTML for debugging
        await self._capture_html_for_debugging(selector, "button")
        print(f"  ❌ Could not click: {selector}")
        raise Exception(f"Failed to click element: {selector}")
    
    def _share_significant_words(self, text1: str, text2: str) -> bool:
        """Check if two texts share significant words (for partial matching)"""
        if not text1 or not text2:
            return False
        
        # Extract significant words (ignore common words like "the", "a", "an")
        common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        words1 = set(word for word in text1.lower().split() if word not in common_words and len(word) > 2)
        words2 = set(word for word in text2.lower().split() if word not in common_words and len(word) > 2)
        
        # Check if they share at least 2 significant words, or if one is a subset of the other
        shared_words = words1.intersection(words2)
        if len(shared_words) >= 2:
            return True
        if len(words1) > 0 and len(words2) > 0:
            # Check if one is mostly contained in the other (e.g., "Create issue" in "Create new issue")
            if words1.issubset(words2) or words2.issubset(words1):
                return True
        
        return False
    
    async def type(self, selector: str, text: str):
        """Type text into an input field - tries multiple strategies including contenteditable divs"""
        print(f"  → Typing \"{text}\" into: {selector}")
        
        # First, wait for any modal/dialog to appear (common after clicking buttons)
        try:
            await self.wait_for_modal()
            await asyncio.sleep(0.5)  # Give modal time to fully render
        except Exception:
            pass  # No modal, continue
        
        # Clean up selector - remove common prefixes
        clean_selector = selector.replace("name=", "").replace("id=", "").replace("textarea=", "").strip("'\"")
        
        # Strategy 0: Try contenteditable elements (common in modern rich text editors)
        try:
            # Find contenteditable elements by aria-label
            # Use general patterns: look for aria-label containing the selector or common field names
            common_field_names = ["name", "title", "description", "text", "input"]
            contenteditable_selectors = [
                f'[contenteditable="true"][aria-label*="{clean_selector}"]',
                f'[role="textbox"][aria-label*="{clean_selector}"]',
            ]
            # Add selectors for common field names if selector is generic
            if not clean_selector or len(clean_selector.split()) <= 1:
                for field_name in common_field_names:
                    contenteditable_selectors.extend([
                        f'[contenteditable="true"][aria-label*="{field_name}"]',
                        f'[role="textbox"][aria-label*="{field_name}"]',
                    ])
            
            for ce_selector in contenteditable_selectors:
                try:
                    element = await self.page.query_selector(ce_selector)
                    if element:
                        # Click to focus
                        await element.click()
                        await asyncio.sleep(0.2)
                        # Type into contenteditable
                        await element.type(text, delay=50)
                        print(f"  ✅ Typed into contenteditable element")
                        await asyncio.sleep(0.3)
                        return
                except Exception:
                    continue
            
            # Try finding contenteditable in modal
            modal_selectors = ['[role="dialog"]', '.modal', '[class*="Modal"]', '[class*="Dialog"]']
            for modal_selector in modal_selectors:
                try:
                    modal = await self.page.query_selector(modal_selector)
                    if modal:
                        # Find contenteditable in modal
                        ce_elements = await modal.query_selector_all('[contenteditable="true"], [role="textbox"]')
                        for ce in ce_elements[:3]:  # Try first 3
                            try:
                                aria_label = await ce.get_attribute("aria-label") or ""
                                # Match if aria-label contains the selector, or if it's a common input field pattern
                                matches_selector = clean_selector.lower() in aria_label.lower() if clean_selector else False
                                is_common_field = any(word in aria_label.lower() for word in ["name", "title", "description", "text", "input"])
                                if matches_selector or is_common_field or not clean_selector:
                                    await ce.click()
                                    await asyncio.sleep(0.2)
                                    await ce.type(text, delay=50)
                                    print(f"  ✅ Typed into contenteditable in modal (aria-label: {aria_label})")
                                    await asyncio.sleep(0.3)
                                    return
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            pass
        
        # Strategy 1: Try direct selector
        try:
            await self.page.fill(selector, text, timeout=3000)
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass
        
        # Strategy 2: Try finding by name attribute (with and without quotes)
        for name_selector in [
            f'input[name="{clean_selector}"]',
            f'input[name={clean_selector}]',
            f'input[name*="{clean_selector}"]',
            f'input[name*={clean_selector}]'
        ]:
            try:
                await self.page.fill(name_selector, text, timeout=3000)
                await asyncio.sleep(0.3)
                return
            except Exception:
                pass
        
        # Strategy 3: Try finding by id
        for id_selector in [
            f'input#{clean_selector}',
            f'input[id="{clean_selector}"]',
            f'input[id*="{clean_selector}"]'
        ]:
            try:
                await self.page.fill(id_selector, text, timeout=3000)
                await asyncio.sleep(0.3)
                return
            except Exception:
                pass
        
        # Strategy 4: Try finding by placeholder or aria-label
        for attr_selector in [
            f'input[placeholder*="{clean_selector}"]',
            f'input[aria-label*="{clean_selector}"]',
            f'input[placeholder*="{text}"]',
            f'input[aria-label*="{text}"]'
        ]:
            try:
                await self.page.fill(attr_selector, text, timeout=3000)
                await asyncio.sleep(0.3)
                return
            except Exception:
                pass
        
        # Strategy 5: Try contenteditable elements (common in modern rich text editors)
        try:
            # Find contenteditable elements by aria-label
            # Use general patterns: look for aria-label containing the selector or common field names
            common_field_names = ["name", "title", "description", "text", "input"]
            contenteditable_selectors = [
                f'[contenteditable="true"][aria-label*="{clean_selector}"]',
                f'[role="textbox"][aria-label*="{clean_selector}"]',
            ]
            # Add selectors for common field names if selector is generic
            if not clean_selector or len(clean_selector.split()) <= 1:
                for field_name in common_field_names:
                    contenteditable_selectors.extend([
                        f'[contenteditable="true"][aria-label*="{field_name}"]',
                        f'[role="textbox"][aria-label*="{field_name}"]',
                    ])
            
            for ce_selector in contenteditable_selectors:
                try:
                    element = await self.page.query_selector(ce_selector)
                    if element and await element.is_visible():
                        # Click to focus
                        await element.click()
                        await asyncio.sleep(0.2)
                        # Clear any existing content first
                        await element.evaluate("el => el.textContent = ''")
                        # Type into contenteditable
                        await element.type(text, delay=50)
                        print(f"  ✅ Typed into contenteditable element")
                        await asyncio.sleep(0.3)
                        return
                except Exception:
                    continue
            
            # Try finding contenteditable in modal
            modal_selectors = ['[role="dialog"]', '.modal', '[class*="Modal"]', '[class*="Dialog"]']
            for modal_selector in modal_selectors:
                try:
                    modal = await self.page.query_selector(modal_selector)
                    if modal:
                        # Find contenteditable in modal
                        ce_elements = await modal.query_selector_all('[contenteditable="true"], [role="textbox"]')
                        for ce in ce_elements[:5]:  # Try first 5
                            try:
                                if await ce.is_visible():
                                    aria_label = (await ce.get_attribute("aria-label") or "").lower()
                                    # Match if aria-label contains the selector, or if it's a common input field pattern
                                    matches_selector = clean_selector.lower() in aria_label.lower() if clean_selector else False
                                    is_common_field = any(word in aria_label.lower() for word in ["name", "title", "description", "text", "input", "value", "field"])
                                    if matches_selector or is_common_field or not clean_selector:
                                        await ce.click()
                                        await asyncio.sleep(0.2)
                                        # Clear existing content
                                        await ce.evaluate("el => el.textContent = ''")
                                        await ce.type(text, delay=50)
                                        print(f"  ✅ Typed into contenteditable in modal (aria-label: {aria_label})")
                                        await asyncio.sleep(0.3)
                                        return
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception as e:
            print(f"  ⚠️  Error with contenteditable strategy: {e}")
            pass
        
        # Strategy 6: Find all inputs and try to match by context
        try:
            inputs = await self._find_inputs_by_context(clean_selector, text)
            if inputs:
                for input_info in inputs:
                    try:
                        # Check if it's a contenteditable
                        if input_info.get("info", {}).get("elementType") == "contenteditable":
                            selector = input_info["selector"]
                            element = await self.page.query_selector(selector)
                            if element:
                                await element.click()
                                await asyncio.sleep(0.2)
                                await element.evaluate("el => el.textContent = ''")
                                await element.type(text, delay=50)
                                print(f"  ✅ Found contenteditable using context: {selector}")
                                await asyncio.sleep(0.3)
                                return
                        else:
                            await self.page.fill(input_info["selector"], text, timeout=3000)
                            print(f"  ✅ Found input using context: {input_info['selector']}")
                            await asyncio.sleep(0.3)
                            return
                    except Exception:
                        continue
        except Exception:
            pass
        
        # Strategy 6: Try textarea elements
        for textarea_selector in [
            f'textarea[name="{clean_selector}"]',
            f'textarea[name*="{clean_selector}"]',
            f'textarea[placeholder*="{clean_selector}"]',
            f'textarea[aria-label*="{clean_selector}"]'
        ]:
            try:
                await self.page.fill(textarea_selector, text, timeout=3000)
                await asyncio.sleep(0.3)
                return
            except Exception:
                pass
        
        # Strategy 7: Find first visible input/textarea/contenteditable in modal or form
        try:
            # First, try to find inputs specifically in modals/dialogs
            modal_selectors = [
                '[role="dialog"]',
                '.modal',
                '[class*="Modal"]',
                '[class*="Dialog"]',
                '[class*="Overlay"]'
            ]
            
            modal_inputs = []
            modal_contenteditables = []
            for modal_selector in modal_selectors:
                try:
                    modal = await self.page.query_selector(modal_selector)
                    if modal:
                        # Find standard inputs within the modal
                        inputs_in_modal = await modal.query_selector_all('input[type="text"], input[type="email"], input:not([type]), textarea')
                        modal_inputs.extend(inputs_in_modal)
                        
                        # Find contenteditable elements (common in modern rich text editors)
                        ce_in_modal = await modal.query_selector_all('[contenteditable="true"], [role="textbox"]')
                        modal_contenteditables.extend(ce_in_modal)
                        print(f"  🔍 Found {len(inputs_in_modal)} inputs and {len(ce_in_modal)} contenteditable elements in modal ({modal_selector})")
                except Exception:
                    continue
            
            # Try contenteditable elements first (they're often used in modern UIs)
            for ce in modal_contenteditables[:5]:
                try:
                    is_visible = await ce.is_visible()
                    if is_visible:
                        aria_label = (await ce.get_attribute("aria-label") or "").lower()
                        # Check if this is likely the name field
                        matches_selector = clean_selector.lower() in aria_label.lower() if clean_selector else False
                        is_common_field = any(word in aria_label.lower() for word in ["name", "title", "description", "text", "input", "value", "field"])
                        if matches_selector or is_common_field or not clean_selector:
                            await ce.click()
                            await asyncio.sleep(0.2)
                            await ce.type(text, delay=50)
                            print(f"  ✅ Found and typed into contenteditable element (aria-label: {aria_label})")
                            await asyncio.sleep(0.3)
                            return
                except Exception:
                    continue
            
            # If no modal inputs, search entire page
            if not modal_inputs:
                modal_inputs = await self.page.query_selector_all('input[type="text"], input[type="email"], input:not([type]), textarea')
            
            # Try each input
            for inp in modal_inputs[:10]:  # Try first 10 inputs
                try:
                    is_visible = await inp.is_visible()
                    if is_visible:
                        # Get input attributes for matching
                        value = await inp.input_value()
                        placeholder = (await inp.get_attribute("placeholder") or "").lower()
                        name_attr = (await inp.get_attribute("name") or "").lower()
                        id_attr = (await inp.get_attribute("id") or "").lower()
                        aria_label = (await inp.get_attribute("aria-label") or "").lower()
                        
                        # Check if this input matches our search term or is likely the right one
                        search_lower = clean_selector.lower()
                        text_lower = text.lower()
                        
                        matches = (
                            search_lower in name_attr or
                            search_lower in id_attr or
                            search_lower in placeholder or
                            search_lower in aria_label or
                            # General pattern: check if placeholder contains common input field words
                            any(word in placeholder for word in ["name", "title", "description", "text", "input", "value", "field"])
                        )
                        
                        # If it's empty or matches, try to fill it
                        if not value and (matches or not clean_selector):
                            await inp.fill(text)
                            print(f"  ✅ Found and filled input by visibility and context")
                            await asyncio.sleep(0.3)
                            return
                except Exception as e:
                    continue
        except Exception as e:
            print(f"  ⚠️  Error in Strategy 7: {e}")
            pass
        
        # If all strategies fail, capture HTML and raise error
        await self._capture_html_for_debugging(selector, "input")
        print(f"  ❌ Could not type into: {selector}")
        raise Exception(f"Failed to type into element: {selector}")
    
    async def _find_inputs_by_context(self, search_term: str, text: str) -> list:
        """Find input fields by analyzing page context"""
        try:
            # Get all input elements with their attributes
            inputs_info = await self.page.evaluate("""
                () => {
                    const inputs = [];
                    document.querySelectorAll('input, textarea').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) { // Only visible
                            inputs.push({
                                name: el.name || '',
                                id: el.id || '',
                                placeholder: el.placeholder || '',
                                type: el.type || 'text',
                                ariaLabel: el.getAttribute('aria-label') || '',
                                className: el.className || '',
                                visible: rect.width > 0 && rect.height > 0
                            });
                        }
                    });
                    return inputs;
                }
            """)
            
            # Score inputs based on relevance
            scored_inputs = []
            search_lower = search_term.lower()
            text_lower = text.lower()
            
            for inp in inputs_info:
                score = 0
                selector = None
                element_type = inp.get("elementType", "input")
                
                # Prioritize inputs in modals (they're likely the ones we want)
                if inp.get("inModal", False):
                    score += 15
                
                # Prioritize empty inputs
                if not inp.get("value"):
                    score += 5
                
                # Prioritize contenteditable elements (common in modern UIs)
                if element_type == "contenteditable":
                    score += 10
                
                # Check name (for standard inputs)
                if inp["name"]:
                    if search_lower in inp["name"].lower():
                        score += 10
                    if "name" in inp["name"].lower() or "title" in inp["name"].lower():
                        score += 5
                    selector = f'input[name="{inp["name"]}"]'
                    if inp.get("type") == "textarea":
                        selector = f'textarea[name="{inp["name"]}"]'
                
                # Check placeholder (for standard inputs)
                if inp["placeholder"]:
                    if search_lower in inp["placeholder"].lower() or text_lower in inp["placeholder"].lower():
                        score += 8
                    common_field_words = ["name", "title", "description", "text", "input", "value", "field", "content"]
                    if any(word in inp["placeholder"].lower() for word in common_field_words):
                        score += 4
                
                # Check aria-label (works for both inputs and contenteditable)
                if inp["ariaLabel"]:
                    aria_lower = inp["ariaLabel"].lower()
                    if search_lower in aria_lower:
                        score += 12  # Higher score for aria-label match
                    # Bonus for common input field patterns
                    common_field_words = ["name", "title", "description", "text", "input", "value", "field", "content"]
                    if any(word in aria_lower for word in common_field_words):
                        score += 8
                    
                    # Create selector based on element type
                    if element_type == "contenteditable":
                        selector = f'[contenteditable="true"][aria-label="{inp["ariaLabel"]}"]'
                    elif not selector:
                        selector = f'input[aria-label="{inp["ariaLabel"]}"]'
                
                # Check id
                if inp["id"]:
                    if search_lower in inp["id"].lower():
                        score += 6
                    if not selector:
                        if element_type == "contenteditable":
                            selector = f'[contenteditable="true"]#{inp["id"]}'
                        else:
                            tag = "textarea" if inp.get("type") == "textarea" else "input"
                            selector = f'{tag}#{inp["id"]}'
                
                # For contenteditable without specific selector, use aria-label
                if element_type == "contenteditable" and not selector and inp["ariaLabel"]:
                    selector = f'[contenteditable="true"][aria-label*="{inp["ariaLabel"]}"]'
                
                # If no specific selector but input is in modal and empty, still include it
                if not selector and inp.get("inModal", False) and not inp.get("value"):
                    if element_type == "contenteditable" and inp["ariaLabel"]:
                        selector = f'[contenteditable="true"][aria-label*="{inp["ariaLabel"]}"]'
                    elif inp["name"]:
                        tag = "textarea" if "textarea" in inp.get("className", "").lower() else "input"
                        selector = f'{tag}[name="{inp["name"]}"]'
                    elif inp["id"]:
                        tag = "textarea" if "textarea" in inp.get("className", "").lower() else "input"
                        selector = f'{tag}#{inp["id"]}'
                
                if selector:
                    scored_inputs.append({
                        "selector": selector,
                        "score": score,
                        "info": inp
                    })
            
            # Sort by score and return top matches
            scored_inputs.sort(key=lambda x: x["score"], reverse=True)
            return scored_inputs[:3]  # Return top 3 matches
            
        except Exception as e:
            print(f"  ⚠️  Error finding inputs by context: {e}")
            return []
    
    async def _extract_all_interactive_elements(self) -> dict:
        """Extract all interactive elements from the page with full attributes"""
        try:
            elements_data = await self.page.evaluate("""
                () => {
                    const elements = {
                        buttons: [],
                        inputs: [],
                        selects: [],
                        links: [],
                        dropdowns: [],
                        contenteditables: [],
                        options: []
                    };
                    
                    // Extract buttons
                    document.querySelectorAll('button, [role="button"], [onclick], a[href]').forEach(el => {
                        const text = el.textContent?.trim().substring(0, 100) || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const id = el.getAttribute('id') || '';
                        const className = el.className || '';
                        const dataTestId = el.getAttribute('data-testid') || '';
                        const isVisible = el.offsetParent !== null;
                        
                        if (text || ariaLabel || id) {
                            elements.buttons.push({
                                text: text,
                                ariaLabel: ariaLabel,
                                id: id,
                                className: className,
                                dataTestId: dataTestId,
                                tag: el.tagName,
                                visible: isVisible,
                                selectors: {
                                    text: text ? `text=${text.substring(0, 50)}` : null,
                                    ariaLabel: ariaLabel ? `[aria-label="${ariaLabel}"]` : null,
                                    id: id ? `#${id}` : null,
                                    dataTestId: dataTestId ? `[data-testid="${dataTestId}"]` : null
                                }
                            });
                        }
                    });
                    
                    // Extract inputs and textareas
                    document.querySelectorAll('input, textarea').forEach(el => {
                        const type = el.getAttribute('type') || 'text';
                        const name = el.getAttribute('name') || '';
                        const id = el.getAttribute('id') || '';
                        const placeholder = el.getAttribute('placeholder') || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const value = el.value || '';
                        const isVisible = el.offsetParent !== null;
                        
                        elements.inputs.push({
                            type: type,
                            name: name,
                            id: id,
                            placeholder: placeholder,
                            ariaLabel: ariaLabel,
                            value: value,
                            tag: el.tagName,
                            visible: isVisible,
                            selectors: {
                                name: name ? `name=${name}` : null,
                                id: id ? `#${id}` : null,
                                placeholder: placeholder ? `[placeholder="${placeholder}"]` : null,
                                ariaLabel: ariaLabel ? `[aria-label="${ariaLabel}"]` : null
                            }
                        });
                    });
                    
                    // Extract contenteditable elements
                    document.querySelectorAll('[contenteditable="true"], [role="textbox"]').forEach(el => {
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const id = el.getAttribute('id') || '';
                        const role = el.getAttribute('role') || '';
                        const className = el.className || '';
                        const textContent = el.textContent?.trim() || '';
                        const isVisible = el.offsetParent !== null;
                        
                        elements.contenteditables.push({
                            ariaLabel: ariaLabel,
                            id: id,
                            role: role,
                            className: className,
                            textContent: textContent,
                            visible: isVisible,
                            selectors: {
                                ariaLabel: ariaLabel ? `[contenteditable="true"][aria-label="${ariaLabel}"]` : null,
                                id: id ? `[contenteditable="true"]#${id}` : null,
                                role: role ? `[role="${role}"][aria-label="${ariaLabel}"]` : null
                            }
                        });
                    });
                    
                    // Extract dropdown options (for custom dropdowns)
                    document.querySelectorAll('[role="option"], li[role="option"]').forEach(el => {
                        const text = el.textContent?.trim() || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const id = el.getAttribute('id') || '';
                        const dataValue = el.getAttribute('data-value') || '';
                        const isVisible = el.offsetParent !== null;
                        
                        if (text || ariaLabel) {
                            elements.options.push({
                                text: text,
                                ariaLabel: ariaLabel,
                                id: id,
                                dataValue: dataValue,
                                visible: isVisible,
                                selectors: {
                                    text: text ? `[role="option"]:has-text("${text}")` : null,
                                    ariaLabel: ariaLabel ? `[aria-label="${ariaLabel}"]` : null,
                                    id: id ? `#${id}` : null
                                }
                            });
                        }
                    });
                    
                    // Extract select elements
                    document.querySelectorAll('select').forEach(el => {
                        const name = el.getAttribute('name') || '';
                        const id = el.getAttribute('id') || '';
                        const options = Array.from(el.options).map(opt => ({
                            value: opt.value,
                            text: opt.text
                        }));
                        
                        elements.selects.push({
                            name: name,
                            id: id,
                            options: options,
                            selectors: {
                                name: name ? `name=${name}` : null,
                                id: id ? `#${id}` : null
                            }
                        });
                    });
                    
                    return elements;
                }
            """)
            return elements_data
        except Exception as e:
            print(f"  ⚠️  Error extracting elements: {e}")
            return {}
    
    async def _capture_html_for_debugging(self, selector: str, element_type: str = "element"):
        """Capture HTML structure when element finding fails"""
        try:
            html_dir = Path("debug_html")
            html_dir.mkdir(exist_ok=True)
            
            timestamp = int(datetime.now().timestamp() * 1000)
            html_file = html_dir / f"error-{element_type}-{timestamp}.html"
            
            # Get page HTML
            html_content = await self.page.content()
            
            # Extract all interactive elements
            all_elements = await self._extract_all_interactive_elements()
            
            # Also try to find similar elements (for backwards compatibility)
            similar_elements = []
            if element_type == "input":
                # First, check for inputs in modals (including contenteditable)
                modal_selectors = ['[role="dialog"]', '.modal', '[class*="Modal"]', '[class*="Dialog"]']
                modal_found = False
                
                for modal_selector in modal_selectors:
                    try:
                        modal = await self.page.query_selector(modal_selector)
                        if modal:
                            modal_found = True
                            print(f"  🔍 Found modal: {modal_selector}")
                            # Find standard inputs within modal
                            inputs = await modal.query_selector_all("input, textarea")
                            # Find contenteditable elements
                            contenteditables = await modal.query_selector_all('[contenteditable="true"], [role="textbox"]')
                            print(f"  📝 Found {len(inputs)} inputs and {len(contenteditables)} contenteditable elements in modal")
                            
                            # Process standard inputs
                            for inp in inputs:
                                try:
                                    is_visible = await inp.is_visible()
                                    if is_visible:
                                        name = await inp.get_attribute("name")
                                        placeholder = await inp.get_attribute("placeholder")
                                        input_type = await inp.get_attribute("type") or "text"
                                        input_id = await inp.get_attribute("id")
                                        aria_label = await inp.get_attribute("aria-label")
                                        tag_name = await inp.evaluate("el => el.tagName")
                                        value = await inp.input_value()
                                        
                                        similar_elements.append({
                                            "name": name,
                                            "placeholder": placeholder,
                                            "type": input_type,
                                            "id": input_id,
                                            "aria-label": aria_label,
                                            "tag": tag_name,
                                            "visible": is_visible,
                                            "value": value,
                                            "inModal": True,
                                            "elementType": "input"
                                        })
                                except Exception as e:
                                    pass
                            
                            # Process contenteditable elements
                            for ce in contenteditables:
                                try:
                                    is_visible = await ce.is_visible()
                                    if is_visible:
                                        aria_label = await ce.get_attribute("aria-label") or ""
                                        contenteditable = await ce.get_attribute("contenteditable")
                                        role = await ce.get_attribute("role")
                                        class_name = await ce.get_attribute("class") or ""
                                        ce_id = await ce.get_attribute("id") or ""
                                        # Get text content
                                        text_content = await ce.text_content() or ""
                                        
                                        similar_elements.append({
                                            "name": None,
                                            "placeholder": None,
                                            "type": "contenteditable",
                                            "id": ce_id,
                                            "aria-label": aria_label,
                                            "tag": await ce.evaluate("el => el.tagName"),
                                            "visible": is_visible,
                                            "value": text_content,
                                            "inModal": True,
                                            "elementType": "contenteditable",
                                            "contenteditable": contenteditable,
                                            "role": role,
                                            "class": class_name
                                        })
                                except Exception as e:
                                    pass
                            
                            break  # Found modal, no need to check others
                    except:
                        continue
                
                # If no modal found, search entire page
                if not modal_found:
                    print("  🔍 No modal found, searching entire page")
                    inputs = await self.page.query_selector_all("input, textarea")
                    for inp in inputs[:20]:  # Check more inputs
                        try:
                            is_visible = await inp.is_visible()
                            if is_visible:  # Only include visible inputs
                                name = await inp.get_attribute("name")
                                placeholder = await inp.get_attribute("placeholder")
                                input_type = await inp.get_attribute("type") or "text"
                                input_id = await inp.get_attribute("id")
                                aria_label = await inp.get_attribute("aria-label")
                                tag_name = await inp.evaluate("el => el.tagName")
                                value = await inp.input_value()
                                
                                similar_elements.append({
                                    "name": name,
                                    "placeholder": placeholder,
                                    "type": input_type,
                                    "id": input_id,
                                    "aria-label": aria_label,
                                    "tag": tag_name,
                                    "visible": is_visible,
                                    "value": value,
                                    "inModal": False
                                })
                        except:
                            pass
            
            # Save HTML with metadata including all extracted elements
            debug_info = f"""<!--
Error trying to find: {selector}
Element type: {element_type}
Timestamp: {datetime.now().isoformat()}
Similar elements found: {json.dumps(similar_elements, indent=2)}
All interactive elements: {json.dumps(all_elements, indent=2)}
-->

{html_content}
"""
            
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(debug_info)
            
            print(f"  🔍 HTML structure saved to: {html_file}")
            print(f"  💡 Found {len(similar_elements)} similar {element_type} elements")
            
            # Display all available interactive elements
            if all_elements:
                total_elements = (
                    len(all_elements.get('buttons', [])) +
                    len(all_elements.get('inputs', [])) +
                    len(all_elements.get('contenteditables', [])) +
                    len(all_elements.get('options', []))
                )
                print(f"  📋 Found {total_elements} total interactive elements on page")
                
                # Show relevant elements based on element_type
                if element_type == "input" or element_type == "type":
                    if all_elements.get('inputs'):
                        visible_inputs = [inp for inp in all_elements['inputs'] if inp.get('visible')]
                        if visible_inputs:
                            print("  📝 Available inputs:")
                            for inp in visible_inputs[:5]:
                                print(f"     - [input] name: {inp.get('name') or 'None'}, id: {inp.get('id') or 'None'}, placeholder: {inp.get('placeholder') or 'None'}, aria-label: {inp.get('ariaLabel') or 'None'}")
                    if all_elements.get('contenteditables'):
                        visible_ce = [ce for ce in all_elements['contenteditables'] if ce.get('visible')]
                        if visible_ce:
                            print("  📝 Available contenteditable elements:")
                            for ce in visible_ce[:5]:
                                print(f"     - [contenteditable] aria-label: '{ce.get('ariaLabel') or 'None'}', id: {ce.get('id') or 'None'}, role: {ce.get('role') or 'None'}")
                elif element_type == "button" or element_type == "click":
                    if all_elements.get('buttons'):
                        visible_buttons = [btn for btn in all_elements['buttons'] if btn.get('visible')]
                        if visible_buttons:
                            print("  🔘 Available buttons:")
                            for btn in visible_buttons[:10]:
                                text = btn.get('text', '')[:50] or 'None'
                                aria = btn.get('ariaLabel') or 'None'
                                print(f"     - [button] text: '{text}', aria-label: '{aria}', id: {btn.get('id') or 'None'}")
                elif element_type == "select" or element_type == "option":
                    if all_elements.get('options'):
                        visible_options = [opt for opt in all_elements['options'] if opt.get('visible')]
                        if visible_options:
                            print("  📋 Available dropdown options:")
                            for opt in visible_options[:10]:
                                text = opt.get('text', '')[:50] or 'None'
                                aria = opt.get('ariaLabel') or 'None'
                                print(f"     - [option] text: '{text}', aria-label: '{aria}', id: {opt.get('id') or 'None'}")
            
            if similar_elements:
                print("  📋 Similar elements (legacy format):")
                for elem in similar_elements[:10]:
                    elem_type = elem.get('elementType', 'input')
                    if elem_type == 'contenteditable':
                        aria_label = elem.get('aria-label') or 'None'
                        ce_id = elem.get('id') or 'None'
                        visible = elem.get('visible', False)
                        role = elem.get('role') or 'None'
                        value = elem.get('value', '') or ''
                        print(f"     - [contenteditable] aria-label: '{aria_label}', id: {ce_id}, role: {role}, visible: {visible}, current_value: '{value[:50]}'")
                    else:
                        name = elem.get('name') or 'None'
                        elem_id = elem.get('id') or 'None'
                        placeholder = elem.get('placeholder') or 'None'
                        aria_label = elem.get('aria-label') or 'None'
                        print(f"     - [input/textarea] name: {name}, id: {elem_id}, placeholder: {placeholder}, aria-label: {aria_label}")
            
            return all_elements
            
        except Exception as e:
            print(f"  ⚠️  Could not capture HTML: {e}")
            return {}
    
    async def wait_for(self, selector: str):
        """Wait for an element to appear"""
        print(f"  → Waiting for: {selector}")
        
        try:
            await self.page.wait_for_selector(selector, timeout=10000)
        except Exception:
            try:
                # Try waiting for text content
                await self.page.wait_for_selector(f"text={selector}", timeout=10000)
            except Exception:
                print(f"  ⚠️  Element not found: {selector}")
    
    async def select(self, selector: str, value: str):
        """Select an option from a dropdown (handles both standard select and custom dropdowns)"""
        print(f"  → Selecting \"{value}\" from: {selector}")
        
        # First, try standard HTML select element
        try:
            await self.page.select_option(selector, value, timeout=3000)
            await asyncio.sleep(0.5)
            return
        except Exception:
            pass
        
        # For custom dropdowns, we need to:
        # 1. Click on the dropdown trigger (the selector) to open it
        # 2. Wait for dropdown options to appear
        # 3. Click on the option with the matching value
        
        # Step 1: Try to click the dropdown trigger/button
        dropdown_clicked = False
        try:
            # Try various ways to find and click the dropdown trigger
            trigger_selectors = [
                selector,  # Original selector
                f'button:has-text("{selector}")',
                f'[aria-label*="{selector}"]',
                f'[data-testid*="{selector.lower()}"]',
            ]
            
            # Try finding dropdown trigger by matching selector keywords
            # Extract key terms from selector (e.g., "priority" from "name=priority")
            selector_keywords = []
            if "=" in selector:
                # Extract the value part (e.g., "priority" from "name=priority")
                selector_keywords.append(selector.split("=")[-1].lower())
            else:
                # Use the whole selector as a keyword
                selector_keywords.append(selector.lower())
            
            # Also try finding by the keyword in various attributes
            for keyword in selector_keywords:
                if keyword and len(keyword) > 2:  # Only use meaningful keywords
                    trigger_selectors.extend([
                        f'button[aria-label*="{keyword}"]',
                        f'[data-testid*="{keyword}"]',
                        f'[class*="{keyword.capitalize()}"]',
                        f'[class*="{keyword}"]',
                        f'button:has([class*="{keyword}"])',
                    ])
            
            for trigger_sel in trigger_selectors:
                try:
                    trigger = await self.page.query_selector(trigger_sel)
                    if trigger and await trigger.is_visible():
                        await trigger.click()
                        print(f"  ✅ Clicked dropdown trigger: {trigger_sel}")
                        dropdown_clicked = True
                        await asyncio.sleep(0.5)  # Wait for dropdown to open
                        break
                except Exception:
                    continue
            
            # If we couldn't find it by selector, try finding by keyword matching
            if not dropdown_clicked and selector_keywords:
                try:
                    # Find all buttons and clickable elements that might be the dropdown trigger
                    buttons = await self.page.query_selector_all('button, [role="button"]')
                    for btn in buttons:
                        try:
                            if await btn.is_visible():
                                text = (await btn.text_content() or "").lower()
                                aria_label = (await btn.get_attribute("aria-label") or "").lower()
                                btn_id = (await btn.get_attribute("id") or "").lower()
                                
                                # Check if button text/aria-label/id contains any of our keywords
                                matches_keyword = any(
                                    keyword in text or keyword in aria_label or keyword in btn_id
                                    for keyword in selector_keywords
                                )
                                
                                # If it matches and is in a form context, it's likely the dropdown trigger
                                if matches_keyword or (not text.strip() and any(keyword in aria_label for keyword in selector_keywords)):
                                    await btn.click()
                                    print(f"  ✅ Clicked dropdown trigger by keyword matching")
                                    dropdown_clicked = True
                                    await asyncio.sleep(0.5)
                                    break
                        except Exception:
                            continue
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"  ⚠️  Could not click dropdown trigger: {e}")
        
        # Step 2: Wait for dropdown to appear (if we clicked the trigger)
        if dropdown_clicked:
            try:
                # Wait for dropdown options to appear
                await self.page.wait_for_selector('[role="option"], [role="listbox"], [class*="Menu"], [class*="Dropdown"]', timeout=3000)
                await asyncio.sleep(0.3)  # Give it a moment to fully render
            except Exception:
                pass  # Dropdown might already be visible or uses different structure
        
        # Step 3: Try finding and clicking the option
        # Try finding the option by text content (case-insensitive, handle "High" vs "high")
        try:
            # Try finding the option by text content
            option_selectors = [
                f'[role="option"]:has-text("{value}")',
                f'[role="option"]:has-text("{value.capitalize()}")',
                f'[role="option"]:has-text("{value.title()}")',
                f'li[role="option"]:has-text("{value}")',
                f'[role="option"] >> text={value}',
                f'[role="option"] >> text={value.capitalize()}',
                f'[role="option"] >> text={value.title()}',
                f'li:has-text("{value}")',
                f'li:has-text("{value.capitalize()}")',
                f'[data-value="{value}"]',
                f'[data-value="{value.lower()}"]',
                f'[id*="{value.lower()}"]',
            ]
            
            for option_selector in option_selectors:
                try:
                    option = await self.page.query_selector(option_selector)
                    if option and await option.is_visible():
                        await option.click()
                        print(f"  ✅ Selected option by clicking: {value}")
                        await asyncio.sleep(0.5)
                        return
                except Exception:
                    continue
            
            # Try finding all options and matching by text (case-insensitive)
            try:
                options = await self.page.query_selector_all('[role="option"], li[role="option"], [class*="MenuItem"]')
                for option in options:
                    try:
                        if await option.is_visible():
                            text_content = (await option.text_content() or "").strip()
                            # Check if the option text matches our value (case-insensitive)
                            value_lower = value.lower()
                            text_lower = text_content.lower()
                            if (value_lower == text_lower or 
                                value_lower in text_lower or 
                                text_lower in value_lower or
                                # Handle "High" vs "high"
                                (value_lower == "high" and "high" in text_lower)):
                                await option.click()
                                print(f"  ✅ Selected option by matching text: {text_content}")
                                await asyncio.sleep(0.5)
                                return
                    except Exception:
                        continue
            except Exception:
                pass
            
            # Try finding by aria-label (for icons with aria-label)
            try:
                # Look for elements with aria-label containing the value
                aria_option = await self.page.query_selector(f'[aria-label*="{value}"]')
                if not aria_option:
                    aria_option = await self.page.query_selector(f'[aria-label*="{value.capitalize()}"]')
                if aria_option:
                    # Find parent option element
                    parent_option = await aria_option.evaluate_handle("""
                        (el) => {
                            let current = el;
                            while (current && current.parentElement) {
                                current = current.parentElement;
                                if (current.getAttribute('role') === 'option' || current.tagName === 'LI') {
                                    return current;
                                }
                            }
                            return null;
                        }
                    """)
                    if parent_option:
                        await parent_option.click()
                        print(f"  ✅ Selected option via aria-label: {value}")
                        await asyncio.sleep(0.5)
                        return
            except Exception:
                pass
        
        except Exception:
            pass  # If all option finding strategies fail, continue to fallback
        
        # If we haven't clicked the trigger yet, try one more time with a broader search
        if not dropdown_clicked:
            print(f"  ⚠️  Could not find dropdown trigger, trying to find option directly...")
            # Maybe the dropdown is already open, try finding options directly
            try:
                options = await self.page.query_selector_all('[role="option"], li[role="option"]')
                for option in options:
                    try:
                        if await option.is_visible():
                            text_content = (await option.text_content() or "").strip()
                            value_lower = value.lower()
                            text_lower = text_content.lower()
                            if (value_lower == text_lower or 
                                value_lower in text_lower or 
                                text_lower in value_lower):
                                await option.click()
                                print(f"  ✅ Selected option directly: {text_content}")
                                await asyncio.sleep(0.5)
                                return
                    except Exception:
                        continue
            except Exception:
                pass
            
        print(f"  ❌ Could not select: {selector} -> {value}")
        raise Exception(f"Failed to select option: {value} from {selector}")
    
    async def wait_for_modal(self):
        """Wait for a modal or overlay to appear"""
        print("  → Waiting for modal/overlay...")
        
        # Common modal selectors
        modal_selectors = [
            '[role="dialog"]',
            '.modal',
            '[class*="Modal"]',
            '[class*="Dialog"]',
            '[class*="Overlay"]',
            '.overlay'
        ]
        
        for selector in modal_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=2000)
                print(f"  ✅ Modal detected: {selector}")
                return
            except Exception:
                # Continue to next selector
                pass
    
    async def is_modal_open(self) -> bool:
        """Check if a modal is currently open"""
        modal_selectors = [
            '[role="dialog"]:visible',
            '.modal:visible',
            '[class*="Modal"]:visible'
        ]
        
        for selector in modal_selectors:
            element = await self.page.query_selector(selector)
            if element:
                return True
        return False
    
    async def is_logged_in(self, url: str) -> bool:
        """Check if user is already logged in by examining the page"""
        try:
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Check for common login indicators (these vary by app)
            # Generally: check if we're redirected away from login page or if user menu exists
            
            # Method 1: Check if we're on a login page
            current_url = self.page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                # Check if there's a login form visible
                login_indicators = [
                    'input[type="email"]',
                    'input[type="password"]',
                    'button:has-text("Sign in")',
                    'button:has-text("Log in")',
                    '[data-testid*="login"]',
                    '[data-testid*="signin"]'
                ]
                
                for indicator in login_indicators:
                    try:
                        element = await self.page.query_selector(indicator)
                        if element and await element.is_visible():
                            return False  # Login form is visible, not logged in
                    except:
                        continue
                
                # If we're on login page but no login form, might be logged in
                return True
            
            # Method 2: Check for logged-in indicators
            logged_in_indicators = [
                '[data-testid*="user-menu"]',
                '[data-testid*="profile"]',
                'button[aria-label*="user"]',
                'button[aria-label*="profile"]',
                'img[alt*="avatar"]',
                'img[alt*="profile"]',
                '.user-menu',
                '.profile-menu'
            ]
            
            for indicator in logged_in_indicators:
                try:
                    element = await self.page.query_selector(indicator)
                    if element and await element.is_visible():
                        return True  # Found logged-in indicator
                except:
                    continue
            
            # Method 3: Check if we have cookies/storage that suggest login
            cookies = await self.context.cookies()
            if cookies:
                # Check for common session/auth cookies
                auth_cookie_names = ['session', 'auth', 'token', 'access', 'jwt', 'sid']
                for cookie in cookies:
                    if any(name in cookie['name'].lower() for name in auth_cookie_names):
                        if cookie.get('value') and len(cookie['value']) > 10:
                            return True  # Has auth cookie with value
            
            # Method 4: Check localStorage for auth tokens
            try:
                storage = await self.page.evaluate("""
                    () => {
                        const keys = Object.keys(localStorage);
                        const authKeys = keys.filter(k => 
                            k.toLowerCase().includes('token') || 
                            k.toLowerCase().includes('auth') ||
                            k.toLowerCase().includes('session') ||
                            k.toLowerCase().includes('user')
                        );
                        return authKeys.length > 0;
                    }
                """)
                if storage:
                    return True
            except:
                pass
            
            # Default: assume not logged in if we can't determine
            return False
            
        except Exception as e:
            print(f"  ⚠️  Error checking login status: {e}")
            return False
    
    async def close(self):
        """Close the browser and save state"""
        if self.context:
            # Save browser state (cookies, localStorage, etc.) for next session
            storage_path = os.getenv("BROWSER_STORAGE_PATH", "browser_storage")
            os.makedirs(storage_path, exist_ok=True)
            state_file = os.path.join(storage_path, "state.json")
            try:
                await self.context.storage_state(path=state_file)
                print(f"💾 Browser state saved to {state_file}")
            except Exception as e:
                print(f"⚠️  Could not save browser state: {e}")
        
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("🔒 Browser closed")

