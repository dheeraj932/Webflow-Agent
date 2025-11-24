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
        print("🌐 Launching Chrome browser with enhanced stealth settings...")
        
        self.playwright = await async_playwright().start()
        
        # Use persistent user data directory for more realistic browser profile
        storage_path = os.getenv("BROWSER_STORAGE_PATH", "browser_storage")
        os.makedirs(storage_path, exist_ok=True)
        user_data_dir = os.path.join(storage_path, "user_data")
        os.makedirs(user_data_dir, exist_ok=True)
        
        # Clean up Chrome singleton lock file if it exists (prevents "File exists" errors)
        singleton_lock = os.path.join(user_data_dir, "SingletonLock")
        singleton_socket = os.path.join(user_data_dir, "SingletonSocket")
        if os.path.exists(singleton_lock):
            try:
                os.remove(singleton_lock)
                print("  🔓 Cleaned up Chrome singleton lock file")
            except Exception as e:
                print(f"  ⚠️  Could not remove singleton lock: {e}")
        if os.path.exists(singleton_socket):
            try:
                os.remove(singleton_socket)
            except Exception:
                pass
        
        # Use Chrome instead of Chromium with enhanced stealth settings
        # launch_persistent_context returns a BrowserContext directly
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",  # Use Chrome instead of Chromium
            headless=os.getenv("HEADLESS", "false").lower() != "false",
            slow_mo=int(os.getenv("SLOW_MO", "100")),
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/Los_Angeles",
            permissions=["geolocation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-translate",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--enable-features=NetworkService,NetworkServiceInProcess",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--use-mock-keychain",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--use-gl=swiftshader",
                "--hide-scrollbars",
                "--mute-audio",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-plugins-discovery",
                "--start-maximized"
            ],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"'
            }
        )
        
        # With persistent context, browser is managed internally
        # Set browser to None since we'll close via context
        self.browser = None
        
        # Get or create the first page
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.context.new_page()
        
        # Enhanced JavaScript injection to hide automation indicators
        await self.page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override the plugins property to mimic a real browser
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: ""},
                            description: "",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                            description: "",
                            filename: "internal-nacl-plugin",
                            length: 2,
                            name: "Native Client"
                        }
                    ];
                    plugins.item = function(index) { return this[index] || null; };
                    plugins.namedItem = function(name) {
                        for (let i = 0; i < this.length; i++) {
                            if (this[i].name === name) return this[i];
                        }
                        return null;
                    };
                    return plugins;
                }
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override chrome property
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override Notification permission
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default'
            });
            
            // Mock getBattery API
            if (navigator.getBattery) {
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                });
            }
            
            // Override toString methods to hide automation
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };
            
            // Override navigator.platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel'
            });
            
            // Override navigator.hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // Override navigator.deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            
            // Override connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
            
            // Remove automation indicators from window
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Override toString to hide automation
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.getBattery || 
                    this === navigator.permissions.query ||
                    this === WebGLRenderingContext.prototype.getParameter) {
                    return 'function () { [native code] }';
                }
                return originalToString.call(this);
            };
            
            // Override document.documentElement.webdriver
            Object.defineProperty(document.documentElement, 'webdriver', {
                get: () => undefined
            });
            
            // Mock missing properties
            if (!window.outerHeight) {
                Object.defineProperty(window, 'outerHeight', {
                    get: () => window.innerHeight
                });
            }
            if (!window.outerWidth) {
                Object.defineProperty(window, 'outerWidth', {
                    get: () => window.innerWidth
                });
            }
        """)
        
        print("✅ Browser initialized with enhanced stealth settings")
    
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
                    
                    # Handle ties: when multiple buttons have the same score,
                    # prefer the one with better semantic match to the target
                    if len(scored_buttons) > 1:
                        top_score = scored_buttons[0]["score"]
                        tied_buttons = [btn for btn in scored_buttons if btn["score"] == top_score]
                        
                        if len(tied_buttons) > 1:
                            # Calculate semantic similarity for tied buttons
                            clean_selector_lower = clean_selector.lower()
                            
                            for btn in tied_buttons:
                                btn_text = (btn["text"] or "").lower()
                                btn_aria = (btn.get("aria_label") or "").lower()
                                            
                                # Calculate semantic similarity score
                                semantic_score = 0
                                
                                # Check how many words from target appear in button text
                                target_words = set(clean_selector_lower.split())
                                btn_words = set((btn_text + " " + btn_aria).split())
                                common_words = target_words.intersection(btn_words)
                                
                                if common_words:
                                    # More common words = better match
                                    semantic_score = len(common_words) * 10
                                    
                                    # Bonus if button text contains key action words from target
                                    action_words = ["add", "create", "new", "task", "issue", "project"]
                                    if any(word in btn_text or word in btn_aria for word in action_words 
                                           if word in clean_selector_lower):
                                        semantic_score += 50
                                
                                # Penalize navigation/accessibility buttons
                                nav_keywords = ["skip", "main content", "accessibility", "navigation"]
                                if any(keyword in btn_text or keyword in btn_aria for keyword in nav_keywords):
                                    semantic_score -= 100
                                
                                btn["semantic_tiebreaker"] = semantic_score
                            
                            # Re-sort tied buttons by semantic score, then by original order
                            tied_buttons.sort(key=lambda x: (x.get("semantic_tiebreaker", 0), scored_buttons.index(x)), reverse=True)
                            
                            # Replace tied buttons in scored_buttons with re-sorted version
                            other_buttons = [btn for btn in scored_buttons if btn["score"] != top_score]
                            scored_buttons = tied_buttons + other_buttons
                            
                            print(f"  🔍 Tie-breaker applied: {len(tied_buttons)} buttons with score {top_score}")
                            for i, btn in enumerate(tied_buttons[:3]):
                                semantic = btn.get("semantic_tiebreaker", 0)
                                text = btn['text'] or btn.get('aria_label', '') or 'No text'
                                print(f"     {i+1}. '{text}' (semantic tie-breaker: {semantic})")
                    
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
        # Use intelligent matching to find the BEST matching field
        try:
            # Find all contenteditable elements in modal first
            modal_selectors = ['[role="dialog"]', '.modal', '[class*="Modal"]', '[class*="Dialog"]']
            modal = None
            for modal_selector in modal_selectors:
                try:
                    modal = await self.page.query_selector(modal_selector)
                    if modal:
                        break
                except Exception:
                    continue
            
            # Get all contenteditable elements (in modal if found, otherwise entire page)
            if modal:
                ce_elements = await modal.query_selector_all('[contenteditable="true"], [role="textbox"]')
            else:
                ce_elements = await self.page.query_selector_all('[contenteditable="true"], [role="textbox"]')
            
            if ce_elements:
                # Score each contenteditable element to find the best match
                scored_elements = []
                clean_selector_lower = clean_selector.lower()
                
                for ce in ce_elements:
                    try:
                        if not await ce.is_visible():
                            continue
                        
                        aria_label = (await ce.get_attribute("aria-label") or "").strip()
                        aria_label_lower = aria_label.lower()
                        ce_id = (await ce.get_attribute("id") or "").lower()
                        placeholder = (await ce.get_attribute("placeholder") or "").lower()
                        
                        # Get current text content to check if field is already filled
                        current_text = (await ce.text_content() or "").strip()
                        
                        score = 0
                        matched = False
                        
                        # Exact match gets highest score
                        if clean_selector_lower == aria_label_lower:
                            score += 1000
                            matched = True
                        # Word boundary match (e.g., "Title" matches "Issue title" or "Title field")
                        elif clean_selector_lower in aria_label_lower:
                            # Check if it's a whole word match (better than partial)
                            word_pattern = r'\b' + re.escape(clean_selector_lower) + r'\b'
                            if re.search(word_pattern, aria_label_lower):
                                score += 800
                            else:
                                score += 500
                            matched = True
                        # Check if selector starts with aria-label (e.g., "Issue title" matches "title")
                        elif aria_label_lower and clean_selector_lower.startswith(aria_label_lower):
                            score += 400
                            matched = True
                        # Check if aria-label starts with selector (e.g., "title" matches "Title field")
                        elif aria_label_lower.startswith(clean_selector_lower):
                            score += 600
                            matched = True
                        # ID match
                        elif clean_selector_lower in ce_id:
                            score += 300
                            matched = True
                        # Placeholder match
                        elif clean_selector_lower in placeholder:
                            score += 200
                            matched = True
                        
                        if not matched:
                            continue
                        
                        # Prefer empty fields (fields that haven't been filled yet)
                        if not current_text or len(current_text) == 0:
                            score += 200
                        else:
                            # Penalize fields that already have content (unless it's the exact same text)
                            if current_text.lower() != text.lower():
                                score -= 500
                        
                        # Prefer fields in modal context
                        if modal:
                            score += 100
                        
                        scored_elements.append({
                            "element": ce,
                            "score": score,
                            "aria_label": aria_label,
                            "current_text": current_text
                        })
                    except Exception:
                        continue
                
                # Sort by score and use the best match
                if scored_elements:
                    scored_elements.sort(key=lambda x: x["score"], reverse=True)
                    best_match = scored_elements[0]
                    
                    # Show what we found
                    if len(scored_elements) > 1:
                        print(f"  🔍 Found {len(scored_elements)} matching contenteditable fields:")
                        for i, elem in enumerate(scored_elements[:3]):
                            marker = "👉 SELECTED" if i == 0 else ""
                            aria = elem["aria_label"] or "No aria-label"
                            current = elem["current_text"][:30] if elem["current_text"] else "empty"
                            print(f"     {i+1}. aria-label: '{aria}', current: '{current}' (score: {elem['score']}) {marker}")
                    
                    # Type into the best matching field
                    element = best_match["element"]
                    aria_label = best_match["aria_label"]
                    
                    # Clear existing content if it's different from what we want to type
                    current_text = best_match["current_text"]
                    if current_text and current_text.lower() != text.lower():
                        await element.click()
                        await asyncio.sleep(0.1)
                        # Select all and delete
                        await element.evaluate("el => { el.textContent = ''; }")
                        await asyncio.sleep(0.1)
                    
                    await element.click()
                    await asyncio.sleep(0.2)
                    await element.type(text, delay=50)
                    print(f"  ✅ Typed into contenteditable field (aria-label: '{aria_label}')")
                    await asyncio.sleep(0.3)
                    return
        except Exception as e:
            print(f"  ⚠️  Error in contenteditable strategy: {e}")
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
        
        # Strategy 5: Removed - contenteditable elements are now handled in Strategy 0 with intelligent matching
        
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
            # Use intelligent matching like Strategy 0
            if modal_contenteditables:
                scored_ce = []
                clean_selector_lower = clean_selector.lower()
                
                for ce in modal_contenteditables:
                    try:
                        if not await ce.is_visible():
                            continue
                        
                        aria_label = (await ce.get_attribute("aria-label") or "").strip()
                        aria_label_lower = aria_label.lower()
                        current_text = (await ce.text_content() or "").strip()
                        
                        score = 0
                        matched = False
                        
                        # Exact match
                        if clean_selector_lower == aria_label_lower:
                            score += 1000
                            matched = True
                        # Word boundary match
                        elif clean_selector_lower in aria_label_lower:
                            word_pattern = r'\b' + re.escape(clean_selector_lower) + r'\b'
                            if re.search(word_pattern, aria_label_lower):
                                score += 800
                            else:
                                score += 500
                            matched = True
                        # Starts with or contains
                        elif aria_label_lower.startswith(clean_selector_lower):
                            score += 600
                            matched = True
                        elif clean_selector_lower.startswith(aria_label_lower):
                            score += 400
                            matched = True
                        
                        if not matched:
                            continue
                        
                        # Prefer empty fields
                        if not current_text:
                            score += 200
                        elif current_text.lower() != text.lower():
                            score -= 500
                        
                        scored_ce.append({
                            "element": ce,
                            "score": score,
                            "aria_label": aria_label
                        })
                    except Exception:
                        continue
                
                if scored_ce:
                    scored_ce.sort(key=lambda x: x["score"], reverse=True)
                    best_ce = scored_ce[0]
                    element = best_ce["element"]
                    aria_label = best_ce["aria_label"]
                    
                    # Clear if needed
                    current_text = (await element.text_content() or "").strip()
                    if current_text and current_text.lower() != text.lower():
                        await element.evaluate("el => { el.textContent = ''; }")
                    
                    await element.click()
                    await asyncio.sleep(0.2)
                    await element.type(text, delay=50)
                    print(f"  ✅ Found and typed into contenteditable element (aria-label: '{aria_label}')")
                    await asyncio.sleep(0.3)
                    return
            
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
                    
                    // Extract buttons (excluding links)
                    document.querySelectorAll('button, [role="button"], [onclick]').forEach(el => {
                        // Skip if it's actually a link
                        if (el.tagName === 'A' || el.closest('a')) return;
                        
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
                    
                    // Extract links separately
                    document.querySelectorAll('a[href]').forEach(el => {
                        const text = el.textContent?.trim().substring(0, 100) || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const href = el.getAttribute('href') || '';
                        const id = el.getAttribute('id') || '';
                        const className = el.className || '';
                        const isVisible = el.offsetParent !== null;
                        
                        if (text || ariaLabel || href) {
                            elements.links.push({
                                text: text,
                                ariaLabel: ariaLabel,
                                href: href,
                                id: id,
                                className: className,
                                tag: el.tagName,
                                visible: isVisible,
                                selectors: {
                                    text: text ? `text=${text.substring(0, 50)}` : null,
                                    ariaLabel: ariaLabel ? `[aria-label="${ariaLabel}"]` : null,
                                    href: href ? `a[href="${href}"]` : null,
                                    id: id ? `#${id}` : null
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
                    
                    // Extract links (navigation elements)
                    document.querySelectorAll('a[href]').forEach(el => {
                        const text = el.textContent?.trim().substring(0, 100) || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const href = el.getAttribute('href') || '';
                        const id = el.getAttribute('id') || '';
                        const className = el.className || '';
                        const isVisible = el.offsetParent !== null;
                        
                        if (text || ariaLabel || href) {
                            elements.links.push({
                                text: text,
                                ariaLabel: ariaLabel,
                                href: href,
                                id: id,
                                className: className,
                                tag: el.tagName,
                                visible: isVisible,
                                selectors: {
                                    text: text ? `text=${text.substring(0, 50)}` : null,
                                    ariaLabel: ariaLabel ? `[aria-label="${ariaLabel}"]` : null,
                                    href: href ? `a[href="${href}"]` : null,
                                    id: id ? `#${id}` : null
                                }
                            });
                        }
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
        
        # Clean up selector - handle cases where selector might be "text=Medium" (wrong format)
        # If selector starts with "text=", it's likely the value, not the field name
        clean_selector = selector
        if selector.startswith("text="):
            # This is wrong - the selector should be the field name, not the value
            # Try to infer the field name from context or use common patterns
            print(f"  ⚠️  Warning: selector '{selector}' looks like a value, not a field name")
            # Try to find dropdowns in modal that might be the target
            # We'll search for common dropdown field names
            clean_selector = "Priority"  # Common field name, but we'll search more broadly
        else:
            clean_selector = selector.replace("name=", "").replace("id=", "").strip("'\"")
        
        # First, try standard HTML select element
        try:
            await self.page.select_option(clean_selector, value, timeout=3000)
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
                clean_selector,  # Original selector
                f'button:has-text("{clean_selector}")',
                f'[aria-label*="{clean_selector}"]',
                f'[aria-label="{clean_selector}"]',
                f'[data-testid*="{clean_selector.lower()}"]',
            ]
            
            # Try finding dropdown trigger by matching selector keywords
            # Extract key terms from selector (e.g., "priority" from "name=priority")
            selector_keywords = []
            if "=" in clean_selector:
                # Extract the value part (e.g., "priority" from "name=priority")
                selector_keywords.append(clean_selector.split("=")[-1].lower())
            else:
                # Use the whole selector as a keyword
                selector_keywords.append(clean_selector.lower())
            
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
                    # First, try to find in modal context (where dropdowns usually are)
                    modal_selectors = ['[role="dialog"]', '.modal', '[class*="Modal"]', '[class*="Dialog"]']
                    modal = None
                    for modal_selector in modal_selectors:
                        try:
                            modal = await self.page.query_selector(modal_selector)
                            if modal:
                                break
                        except Exception:
                            continue
                    
                    # Search in modal if found, otherwise entire page
                    search_context = modal if modal else self.page
                    
                    # Find all buttons and clickable elements that might be the dropdown trigger
                    buttons = await search_context.query_selector_all('button, [role="button"], [role="combobox"]')
                    scored_buttons = []
                    
                    for btn in buttons:
                        try:
                            if not await btn.is_visible():
                                continue
                            
                            text = (await btn.text_content() or "").strip().lower()
                            aria_label = (await btn.get_attribute("aria-label") or "").strip().lower()
                            btn_id = (await btn.get_attribute("id") or "").lower()
                            btn_class = (await btn.get_attribute("class") or "").lower()
                            
                            score = 0
                            matched = False
                            
                            # Check if button text/aria-label/id contains any of our keywords
                            for keyword in selector_keywords:
                                if keyword in aria_label:
                                    # Exact match in aria-label gets highest score
                                    if keyword == aria_label or aria_label.startswith(keyword):
                                        score += 1000
                                    else:
                                        score += 500
                                    matched = True
                                elif keyword in text:
                                    score += 300
                                    matched = True
                                elif keyword in btn_id:
                                    score += 200
                                    matched = True
                                elif keyword in btn_class:
                                    score += 100
                                    matched = True
                            
                            # Bonus for buttons in modal/form context
                            if modal:
                                score += 100
                            
                            # Bonus for combobox role (common for dropdowns)
                            role = await btn.get_attribute("role")
                            if role == "combobox":
                                score += 200
                            
                            if matched:
                                scored_buttons.append({
                                    "element": btn,
                                    "score": score,
                                    "aria_label": aria_label,
                                    "text": text
                                })
                        except Exception:
                            continue
                    
                    # Sort by score and click the best match
                    if scored_buttons:
                        scored_buttons.sort(key=lambda x: x["score"], reverse=True)
                        best_btn = scored_buttons[0]
                        
                        if len(scored_buttons) > 1:
                            print(f"  🔍 Found {len(scored_buttons)} potential dropdown triggers:")
                            for i, btn_info in enumerate(scored_buttons[:3]):
                                marker = "👉 SELECTED" if i == 0 else ""
                                aria = btn_info["aria_label"] or btn_info["text"] or "No label"
                                print(f"     {i+1}. '{aria}' (score: {btn_info['score']}) {marker}")
                        
                        await best_btn["element"].click()
                        print(f"  ✅ Clicked dropdown trigger: '{best_btn['aria_label'] or best_btn['text']}'")
                        dropdown_clicked = True
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️  Error finding dropdown trigger: {e}")
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
    
    async def discover(self):
        """Discover and list all visible UI elements on the current page"""
        print("  → Discovering visible UI elements...")
        try:
            elements = await self._extract_all_interactive_elements()
            
            print("  📋 Discovered elements:")
            
            # Show buttons
            buttons = elements.get('buttons', [])
            visible_buttons = [b for b in buttons if b.get('visible')]
            if visible_buttons:
                print(f"     Buttons ({len(visible_buttons)}):")
                for btn in visible_buttons[:10]:  # Show first 10
                    text = btn.get('text', '').strip()[:50] or 'No text'
                    aria = btn.get('ariaLabel', '').strip() or 'No aria-label'
                    print(f"       - '{text}' (aria-label: '{aria}')")
            
            # Show links
            links = elements.get('links', [])
            visible_links = [l for l in links if l.get('visible')]
            if visible_links:
                print(f"     Links ({len(visible_links)}):")
                for link in visible_links[:10]:
                    text = link.get('text', '').strip()[:50] or 'No text'
                    href = link.get('href', '')[:50] or 'No href'
                    print(f"       - '{text}' -> {href}")
            
            # Show inputs
            inputs = elements.get('inputs', [])
            visible_inputs = [i for i in inputs if i.get('visible')]
            if visible_inputs:
                print(f"     Inputs ({len(visible_inputs)}):")
                for inp in visible_inputs[:5]:
                    name = inp.get('name', '') or 'No name'
                    placeholder = inp.get('placeholder', '')[:50] or 'No placeholder'
                    print(f"       - name: '{name}', placeholder: '{placeholder}'")
            
            print(f"  ✅ Discovery complete: {len(visible_buttons)} buttons, {len(visible_links)} links, {len(visible_inputs)} inputs")
        except Exception as e:
            print(f"  ⚠️  Error during discovery: {e}")
    
    async def find(self, search_term: str):
        """Find elements matching a search term (semantic search)"""
        print(f"  → Finding elements matching: '{search_term}'")
        try:
            elements = await self._extract_all_interactive_elements()
            search_lower = search_term.lower()
            
            matches = []
            
            # Search in buttons
            buttons = elements.get('buttons', [])
            for btn in buttons:
                if not btn.get('visible'):
                    continue
                text = (btn.get('text', '') or '').lower()
                aria = (btn.get('ariaLabel', '') or '').lower()
                if search_lower in text or search_lower in aria or text in search_lower or aria in search_lower:
                    matches.append({
                        'type': 'button',
                        'text': btn.get('text', ''),
                        'ariaLabel': btn.get('ariaLabel', ''),
                        'selector': f"text={btn.get('text', '')}" if btn.get('text') else f"[aria-label='{btn.get('ariaLabel', '')}']"
                    })
            
            # Search in links
            links = elements.get('links', [])
            for link in links:
                if not link.get('visible'):
                    continue
                text = (link.get('text', '') or '').lower()
                href = (link.get('href', '') or '').lower()
                if search_lower in text or search_lower in href or text in search_lower:
                    matches.append({
                        'type': 'link',
                        'text': link.get('text', ''),
                        'href': link.get('href', ''),
                        'selector': f"text={link.get('text', '')}" if link.get('text') else f"a[href*='{link.get('href', '')[:30]}']"
                    })
            
            if matches:
                print(f"  ✅ Found {len(matches)} matching elements:")
                for i, match in enumerate(matches[:5], 1):
                    print(f"     {i}. {match['type']}: '{match.get('text', match.get('ariaLabel', 'No text'))}'")
            else:
                print(f"  ⚠️  No elements found matching '{search_term}'")
            
            return matches
        except Exception as e:
            print(f"  ⚠️  Error during find: {e}")
            return []
    
    async def extract_text(self):
        """Extract and display visible text from the current page"""
        print("  → Extracting visible text from page...")
        try:
            # Get main content text
            text_content = await self.page.evaluate("""
                () => {
                    // Get text from main content areas
                    const mainContent = document.querySelector('main, [role="main"], .main-content, #main-content');
                    if (mainContent) {
                        return mainContent.innerText || mainContent.textContent || '';
                    }
                    // Fallback to body
                    return document.body.innerText || document.body.textContent || '';
                }
            """)
            
            # Get headings
            headings = await self.page.evaluate("""
                () => {
                    const headings = [];
                    document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
                        if (h.offsetParent !== null) { // Only visible
                            headings.push({
                                level: h.tagName,
                                text: h.textContent.trim()
                            });
                        }
                    });
                    return headings;
                }
            """)
            
            # Get button/link labels
            interactive_labels = await self.page.evaluate("""
                () => {
                    const labels = [];
                    document.querySelectorAll('button, a, [role="button"], [role="link"]').forEach(el => {
                        if (el.offsetParent !== null) { // Only visible
                            const text = el.textContent.trim();
                            const ariaLabel = el.getAttribute('aria-label') || '';
                            if (text || ariaLabel) {
                                labels.push(text || ariaLabel);
                            }
                        }
                    });
                    return labels;
                }
            """)
            
            print("  📄 Page content summary:")
            if headings:
                print("     Headings:")
                for h in headings[:10]:
                    print(f"       {h['level']}: {h['text'][:60]}")
            
            if interactive_labels:
                print(f"     Interactive elements ({len(interactive_labels)}):")
                unique_labels = list(set(interactive_labels))[:15]
                for label in unique_labels:
                    if label:
                        print(f"       - {label[:60]}")
            
            # Show first 200 chars of main content
            if text_content:
                preview = text_content[:200].replace('\n', ' ').strip()
                print(f"     Content preview: {preview}...")
            
            print("  ✅ Text extraction complete")
        except Exception as e:
            print(f"  ⚠️  Error during text extraction: {e}")
    
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
            # For persistent context, state is automatically saved to user_data_dir
            # But we can also save a separate state file for compatibility
            storage_path = os.getenv("BROWSER_STORAGE_PATH", "browser_storage")
            os.makedirs(storage_path, exist_ok=True)
            state_file = os.path.join(storage_path, "state.json")
            try:
                await self.context.storage_state(path=state_file)
                print(f"💾 Browser state saved to {state_file}")
            except Exception as e:
                print(f"⚠️  Could not save browser state: {e}")
            
            # Close the persistent context (this also closes the browser)
            await self.context.close()
        
        # If we have a separate browser instance (non-persistent), close it
        if self.browser and hasattr(self.browser, 'close'):
            try:
                await self.browser.close()
            except Exception:
                pass
        
        if self.playwright:
            await self.playwright.stop()
        print("🔒 Browser closed")

