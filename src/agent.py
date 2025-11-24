"""
Agent B - Main agent that receives tasks and executes them
Interprets natural language tasks and coordinates navigation and screenshot capture
"""

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

from .navigator import Navigator
from .screenshot import ScreenshotCapture

load_dotenv()


class AgentB:
    """Main agent that executes tasks and captures UI states"""
    
    def __init__(self):
        self.navigator = Navigator()
        self.screenshot_capture = ScreenshotCapture()
        self.groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.current_task = None
        self.captured_states = []
    
    async def execute_task(self, task_query: str) -> dict:
        """
        Main method to execute a task from Agent A
        
        Args:
            task_query: Natural language task query (e.g., "How do I create a project in Linear?")
            
        Returns:
            Task execution result with captured states
        """
        print(f"\n🤖 Agent B received task: \"{task_query}\"\n")
        
        self.current_task = task_query
        self.captured_states = []
        
        try:
            # Step 1: Understand the task using AI
            task_plan = await self.understand_task(task_query)
            print(f"📋 Task Plan: {json.dumps(task_plan, indent=2)}")
            
            # Step 2: Initialize browser and navigate to starting URL
            await self.navigator.initialize()
            
            # Navigate to starting URL if provided
            if task_plan.get("startingUrl"):
                print(f"\n🌐 Opening: {task_plan['startingUrl']}")
                await self.navigator.navigate(task_plan["startingUrl"])
                
                # Step 2.5: Check if already logged in, if not, wait for manual login
                is_logged_in = await self.navigator.is_logged_in(task_plan["startingUrl"])
                
                if not is_logged_in:
                    print("\n" + "=" * 60)
                    print("⏸️  PAUSED: Please log in manually in the browser")
                    print("=" * 60)
                    input("Press ENTER after you have logged in to continue...\n")
                else:
                    print("\n✅ Already logged in! Continuing with task execution...\n")
                
                # Capture logged-in state
                login_screenshot = await self.screenshot_capture.capture(
                    self.navigator.page,
                    "logged-in-state",
                    "after-login"
                )
                self.captured_states.append(login_screenshot)
            
            # Step 3: Execute the plan step by step with adaptive error handling
            for step_index, step in enumerate(task_plan["steps"]):
                print(f"\n📍 Executing step {step_index + 1}/{len(task_plan['steps'])}: {step['description']}")
                
                # Capture state before action
                if step.get("captureBefore", False):
                    screenshot = await self.screenshot_capture.capture(
                        self.navigator.page,
                        step["description"],
                        "before"
                    )
                    self.captured_states.append(screenshot)
                
                # Perform the action with retry and adaptation
                max_retries = 2
                retry_count = 0
                step_succeeded = False
                
                while retry_count <= max_retries and not step_succeeded:
                    try:
                        await self.execute_step(step)
                        step_succeeded = True
                    except Exception as e:
                        retry_count += 1
                        print(f"  ⚠️  Step failed (attempt {retry_count}/{max_retries + 1}): {e}")
                        
                        if retry_count <= max_retries:
                            # First, try simple alternative approaches
                            if retry_count == 1:
                                print("  🔍 Attempting to discover alternative approach...")
                                alternative_found = await self._try_alternative_approach(step)
                                if alternative_found:
                                    step_succeeded = True
                                    continue
                            
                            # If simple alternatives didn't work, use AI to analyze and fix
                            if not step_succeeded:
                                print("  🤖 Using AI to analyze page structure and fix selector...")
                                await self._adapt_plan_from_page(task_plan, step_index)
                                # Wait a bit for page to stabilize
                                await asyncio.sleep(0.5)
                        else:
                            # Final attempt failed, raise the error
                            raise e
                
                # Capture state after action
                if step.get("captureAfter", False):
                    screenshot = await self.screenshot_capture.capture(
                        self.navigator.page,
                        step["description"],
                        "after"
                    )
                    self.captured_states.append(screenshot)
                
                # Verify form submissions
                await self._verify_form_submission(step, task_plan)
                
                # Wait for UI to stabilize
                await asyncio.sleep(1)
            
            # Step 4: Final state capture
            final_screenshot = await self.screenshot_capture.capture(
                self.navigator.page,
                "final-state",
                "final"
            )
            self.captured_states.append(final_screenshot)
            
            # Step 5: Save organized dataset
            await self.save_dataset(task_plan)
            
            print(f"\n✅ Task completed! Captured {len(self.captured_states)} UI states.\n")
            
            return {
                "success": True,
                "task": task_query,
                "plan": task_plan,
                "capturedStates": len(self.captured_states),
                "datasetPath": f"dataset/{task_plan['app']}/{task_plan['taskName']}"
            }
            
        except Exception as error:
            print(f"❌ Error executing task: {error}")
            raise
        finally:
            await self.navigator.close()
    
    async def understand_task(self, task_query: str) -> dict:
        """
        Use AI to understand the task and create an execution plan
        
        Args:
            task_query: Natural language task
            
        Returns:
            Structured task plan
        """
        prompt = f"""You are Agent B in a multi-agent system. Agent A sends you natural-language task requests such as:
- “How do I create a project in Linear?”
- “How do I filter a database in Notion?”
- “How do I change workspace settings in Asana?”

Your job:
**Generate a complete, step-by-step execution plan for performing the task in the live web application, including capturing every UI state — even those with no unique URL (modals, drawers, forms, etc.).**

You must return a structured JSON object with:
{{
  "app": "...",
  "taskName": "...",
  "description": "...",
  "startingUrl": "...",
  "steps": [...]
}}

Your output must reflect **deep reasoning, exploration, and generalization**.
This system must NOT rely on hardcoded sequences or app-specific assumptions. It must generalize across ANY web app and ANY unseen task.

=====================================================================
📌 SECTION 1 — CORE PRINCIPLES
=====================================================================

1. **Generalize Across Any App**
   You may encounter Linear, Notion, Asana, Trello, Jira, Monday.com, or unknown apps.
   Therefore:
   - Infer UI layouts and navigation structures.
   - Infer meaning from visible text, labels, roles, ARIA attributes.
   - Never assume app-specific naming.

2. **Generalize Across Any Task**
   Tasks may involve:
   - Create / Add / New
   - Edit / Update
   - Delete / Archive
   - Filter / Search / Sort
   - Navigate between sections
   - Change workspace settings
   - Duplicate / Move / Assign
   Infer workflow based on semantics.

3. **Capture UI States Even Without URLs**
   Many states have no unique URL:
   - Modals
   - Drawers
   - Panels
   - Inline editors
   - Dropdowns
   Capture states before/after interactions when meaningful.

4. **Never Assume the Correct Starting Page**
   Begin with:
   - A navigation step, OR
   - A discovery scan step
   before performing actions.

5. **Use "navigate" ONLY for Full URLs**
   Example:
   `"navigate": "https://linear.app/projects"`
   Never use navigate for clickable elements.

6. **Use "click" for UI Elements**
   Examples:
   - `text=Projects`
   - `text=Add project`
   - `role=button[name='New']`
   - `aria-label=Create task`

7. **Always Use Wait Steps**
   Wait 2–3 seconds after:
   - Modal opens
   - Form submission
   - Navigation change

8. **Use Realistic Input Text**
   Examples:
   - “Sample Project”
   - “Demo Task”
   - “Research Database”

9. **Do NOT Include Login Steps**
   The user is already logged in.

=====================================================================
📌 SECTION 2 — DYNAMIC EXPLORATION & FALLBACKS
=====================================================================

Allowed exploration actions:

- **"discover"**  
  Lists visible:
  - buttons, links, menus
  - headings, sidebar items
  - modal indicators

- **"find"**  
  Semantic matching for:
  - “Create” ~ “Add” ~ “New” ~ “+”

- **"extractText"**  
  Reads visible text to infer:
  - current location
  - modal presence
  - visible lists
  - available actions

- **"conditional"**  
  Execute steps only if element exists.

Fallback rules:
- If “Projects” isn’t found → try “Boards”, “Issues”, “Tasks”, “Pages”.
- If “Create” isn’t found → try “Add”, “New”, “+”.
- If element not clickable → try parent selector.
- If modal doesn’t open → retry after delay.

=====================================================================
📌 SECTION 2.5 — MANDATORY UI LABEL VALIDATION (CRITICAL)
=====================================================================

Before clicking ANY button or actionable element, Agent B MUST:

1. Perform a `"discover"` step to list visible UI elements.
2. Use `"extractText"` to gather ALL visible button/link labels.
3. Perform semantic matching between:
   - the task intent (e.g., “create project”), and
   - visible UI labels (e.g., “Add project”, “New project”, “+ Project”, “Create”).
4. Select the MOST semantically relevant visible label.
5. Use ONLY the real UI label in `"target"`.
6. NEVER assume a button label from the task description.
7. Only click labels confirmed to exist on screen.

Example:
If the visible button is **“Add project”**, you MUST output:
“target”: “text=Add project”
NOT:
"target": "text=Create project"
This rule applies to ALL apps and ALL tasks.

=====================================================================
📌 SECTION 3 — TASK INTERPRETATION LOGIC
=====================================================================

Before generating steps, Agent B MUST:
1. Parse the natural-language request.
2. Identify task intent (create, filter, navigate, delete, configure).
3. Identify target object (project, task, page, database, issue).
4. Identify the app.
5. Build a logical workflow:
   - Navigate to section
   - Discover visible elements
   - Validate UI labels
   - Open modal
   - Fill fields
   - Submit
   - Verify success

=====================================================================
📌 SECTION 4 — JSON OUTPUT FORMAT
=====================================================================

Your result must be JSON like:
```json
{{
  "app": "linear" | "notion" | "asana" | "other",
  "taskName": "short-task-name",
  "description": "brief overview",
  "startingUrl": "https://linear.app" or similar,
  "steps": [
    {{
      "description": "What this step does",
      "action": "navigate" | "click" | "type" | "wait" | "select" |
                "discover" | "find" | "extractText" | "conditional",
      "target": "selector or description",
      "value": "text typed (if any)",
      "captureBefore": true/false,
      "captureAfter": true/false
    }}
  ]
}}

=====================================================================
📌 SECTION 5 — IMPORTANT URL RULES

Linear

Use:
	•	https://linear.app
	•	https://linear.app/projects
	•	https://linear.app/issues
Do NOT navigate to /login.

Notion

Use only:
	•	https://notion.so
	•	https://www.notion.so

Other Apps

Infer full URLs, always starting with https://.

=====================================================================
📌 SECTION 6 — REQUIRED VERIFICATION STEPS

After submissions or UI transitions:
	1.	Wait 2–3 seconds
	2.	Verify modal closed
	3.	Verify new item appears
	4.	Capture updated state

=====================================================================
📌 SECTION 7 — WHAT YOU MUST RETURN

Your final JSON MUST:
✔ Include navigation
✔ Include exploration
✔ Include UI label validation
✔ Use the REAL UI text for buttons
✔ Include captures
✔ Include waits
✔ Handle non-URL states
✔ Work across ANY app
✔ Exclude login steps
✔ Apply deep reasoning
✔ Match real UI

=====================================================================
📌 END OF SYSTEM PROMPT

When ready, analyze the following task query:

Task: “{task_query}”
"""
        
        try:
            response = self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates detailed web automation plans. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            # Validate and enhance the plan
            if not plan.get("steps") or len(plan["steps"]) == 0:
                raise ValueError("Invalid task plan: no steps defined")
            
            # Fix common URL issues
            if plan.get("startingUrl"):
                plan["startingUrl"] = self._fix_url(plan["startingUrl"])
            
            # Fix URLs in steps
            for step in plan.get("steps", []):
                if step.get("action") == "navigate" and step.get("target"):
                    target = step.get("target")
                    # Check if target is a selector (not a URL)
                    if self._is_selector_not_url(target):
                        # Convert navigate action to click when target is a selector
                        print(f"  🔄 Converting navigate to click for selector: {target}")
                        step["action"] = "click"
                    else:
                        # It's a URL, fix it
                        step["target"] = self._fix_url(target)
            
            # Remove login steps since user is already logged in
            plan = self._filter_login_steps(plan)
            
            return plan
        except Exception as error:
            print(f"Error understanding task: {error}")
            # Fallback to a basic plan structure
            return self.create_fallback_plan(task_query)
    
    def _fix_url(self, url: str) -> str:
        """Fix common URL issues"""
        # Fix Linear URLs - replace app.linear.app with linear.app
        if "app.linear.app" in url:
            url = url.replace("app.linear.app", "linear.app")
        # Fix relative URLs for Linear
        if url.startswith("/") and "linear" in self.current_task.lower():
            url = f"https://linear.app{url}"
        return url
    
    def _is_selector_not_url(self, target: str) -> bool:
        """Check if target is a selector (not a URL)"""
        if not target:
            return False
        
        # If it starts with http:// or https://, it's a URL
        if target.startswith(("http://", "https://")):
            return False
        
        # If it starts with common selector prefixes, it's a selector
        selector_prefixes = ["text=", "css=", "xpath=", "#", ".", "[", "button:", "a:", "input:", "select:"]
        if any(target.startswith(prefix) for prefix in selector_prefixes):
            return True
        
        # If it contains spaces or special characters that suggest it's text content, it's likely a selector
        # URLs don't typically have unencoded spaces
        if " " in target and not target.startswith("http"):
            return True
        
        # If it's a single word or short phrase (not a domain), likely a selector
        if len(target.split()) <= 3 and "." not in target.split()[0]:
            return True
        
        return False
    
    def create_fallback_plan(self, task_query: str) -> dict:
        """Create a fallback plan if AI parsing fails"""
        lower_query = task_query.lower()
        
        if "linear" in lower_query:
            return {
                "app": "linear",
                "taskName": "generic-task",
                "description": task_query,
                "startingUrl": "https://linear.app/login",
                "steps": [
                    {"description": "Navigate to Linear", "action": "navigate", "target": "https://linear.app/login", "captureAfter": True},
                    {"description": "Wait for page load", "action": "wait", "target": "body", "captureAfter": False}
                ]
            }
        elif "notion" in lower_query:
            return {
                "app": "notion",
                "taskName": "generic-task",
                "description": task_query,
                "startingUrl": "https://notion.so",
                "steps": [
                    {"description": "Navigate to Notion", "action": "navigate", "target": "https://notion.so", "captureAfter": True},
                    {"description": "Wait for page load", "action": "wait", "target": "body", "captureAfter": False}
                ]
            }
        
        raise ValueError("Could not create task plan. Please provide a valid task query.")
    
    async def execute_step(self, step: dict):
        """Execute a single step from the plan"""
        action = step.get("action")
        target = step.get("target")
        value = step.get("value", "")
        
        # Safety check: if action is "navigate" but target is a selector, convert to click
        if action == "navigate" and target and self._is_selector_not_url(target):
            print(f"  ⚠️  Detected selector in navigate action, converting to click: {target}")
            action = "click"
        
        if action == "navigate":
            await self.navigator.navigate(target)
        elif action == "click":
            await self.navigator.click(target)
        elif action == "type":
            await self.navigator.type(target, value)
        elif action == "wait":
            await self.navigator.wait_for(target)
        elif action == "select":
            await self.navigator.select(target, value)
        else:
            print(f"⚠️  Unknown action: {action}")
    
    async def _try_alternative_approach(self, step: dict) -> bool:
        """Try alternative selectors when a step fails"""
        action = step.get("action")
        target = step.get("target")
        description = step.get("description", "").lower()
        
        if action == "click":
            # Try common alternative patterns
            alternatives = [
                target.replace("'", '"'),  # Fix quote style
                target.replace("text=", "").strip("'\""),  # Remove text= prefix
                f"button:has-text('{target}')",
                f"a:has-text('{target}')",
                f"[aria-label*='{target}']",
            ]
            
            # If looking for "New Project" or "Create", also try finding "Projects" first
            if "project" in description and "new" in description or "create" in description:
                # Try to find navigation to Projects section first
                try:
                    await self.navigator.click("text=Projects")
                    await asyncio.sleep(1)
                    print("  ✅ Found and clicked 'Projects' navigation")
                    # Now try the original target again
                    for alt in alternatives:
                        try:
                            await self.navigator.click(alt)
                            print(f"  ✅ Found alternative selector: {alt}")
                            return True
                        except:
                            continue
                except:
                    pass
            
            # Try alternatives
            for alt in alternatives:
                try:
                    await self.navigator.click(alt)
                    print(f"  ✅ Found alternative selector: {alt}")
                    return True
                except:
                    continue
        
        return False
    
    async def _adapt_plan_from_page(self, task_plan: dict, failed_step_index: int):
        """Analyze current page and adapt the plan using AI"""
        try:
            failed_step = task_plan['steps'][failed_step_index]
            action = failed_step.get('action')
            target = failed_step.get('target', '')
            description = failed_step.get('description', '')
            
            # Extract all interactive elements from the page
            all_elements = await self.navigator._extract_all_interactive_elements()
            
            # Build a comprehensive summary of available elements
            elements_summary_parts = []
            
            if action in ["click", "navigate"]:
                buttons = all_elements.get('buttons', [])
                visible_buttons = [b for b in buttons if b.get('visible')]
                if visible_buttons:
                    elements_summary_parts.append("Buttons:")
                    for btn in visible_buttons[:15]:
                        text = btn.get('text', '').strip()[:50]
                        aria = btn.get('ariaLabel', '').strip()
                        btn_id = btn.get('id', '')
                        selectors = btn.get('selectors', {})
                        selector_str = ", ".join([v for v in selectors.values() if v])
                        elements_summary_parts.append(f"  - Text: '{text}', Aria-label: '{aria}', ID: {btn_id}, Selectors: {selector_str}")
            
            if action in ["type", "input"]:
                inputs = all_elements.get('inputs', [])
                visible_inputs = [i for i in inputs if i.get('visible')]
                if visible_inputs:
                    elements_summary_parts.append("Input fields:")
                    for inp in visible_inputs[:10]:
                        name = inp.get('name', '')
                        placeholder = inp.get('placeholder', '')
                        aria = inp.get('ariaLabel', '')
                        inp_id = inp.get('id', '')
                        selectors = inp.get('selectors', {})
                        selector_str = ", ".join([v for v in selectors.values() if v])
                        elements_summary_parts.append(f"  - Name: {name}, Placeholder: '{placeholder}', Aria-label: '{aria}', ID: {inp_id}, Selectors: {selector_str}")
                
                contenteditables = all_elements.get('contenteditables', [])
                visible_ce = [ce for ce in contenteditables if ce.get('visible')]
                if visible_ce:
                    elements_summary_parts.append("Contenteditable fields:")
                    for ce in visible_ce[:10]:
                        aria = ce.get('ariaLabel', '')
                        ce_id = ce.get('id', '')
                        role = ce.get('role', '')
                        selectors = ce.get('selectors', {})
                        selector_str = ", ".join([v for v in selectors.values() if v])
                        elements_summary_parts.append(f"  - Aria-label: '{aria}', ID: {ce_id}, Role: {role}, Selectors: {selector_str}")
            
            if action in ["select", "option"]:
                options = all_elements.get('options', [])
                visible_options = [opt for opt in options if opt.get('visible')]
                if visible_options:
                    elements_summary_parts.append("Dropdown options:")
                    for opt in visible_options[:15]:
                        text = opt.get('text', '').strip()[:50]
                        aria = opt.get('ariaLabel', '').strip()
                        opt_id = opt.get('id', '')
                        selectors = opt.get('selectors', {})
                        selector_str = ", ".join([v for v in selectors.values() if v])
                        elements_summary_parts.append(f"  - Text: '{text}', Aria-label: '{aria}', ID: {opt_id}, Selectors: {selector_str}")
            
            elements_summary = "\n".join(elements_summary_parts) if elements_summary_parts else "No relevant elements found"
            
            # Use AI to analyze and suggest the correct selector
            adaptation_prompt = f"""The current step failed:
Action: {action}
Target: {target}
Description: {description}

Task goal: {self.current_task}

Available elements on the page:
{elements_summary}

Analyze the failed step and the available elements. Find the correct selector that matches the intended target.
Consider:
- Text content matching (case-insensitive, partial matches)
- Aria-label matching
- ID matching
- The context of the task

Respond with JSON:
{{
  "suggestedAction": "{action}",
  "target": "the correct selector (e.g., text=ButtonName, [aria-label='Label'], #id, etc.)",
  "reason": "explanation of why this selector matches the intended target",
  "confidence": "high" | "medium" | "low"
}}"""
            
            response = self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a web automation expert that analyzes page structure and suggests correct selectors. Always respond with valid JSON only. Be precise with selectors."},
                    {"role": "user", "content": adaptation_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            suggestion = json.loads(response.choices[0].message.content)
            print(f"  💡 AI analysis: {suggestion.get('reason')}")
            print(f"  📊 Confidence: {suggestion.get('confidence', 'unknown')}")
            
            # Update the failed step with the suggestion
            if suggestion.get("target"):
                old_target = task_plan["steps"][failed_step_index]["target"]
                task_plan["steps"][failed_step_index]["target"] = suggestion["target"]
                print(f"  🔄 Updated selector: '{old_target}' -> '{suggestion['target']}'")
                
                # If action needs to change, update it
                if suggestion.get("suggestedAction") and suggestion["suggestedAction"] != action:
                    task_plan["steps"][failed_step_index]["action"] = suggestion["suggestedAction"]
                    print(f"  🔄 Updated action: '{action}' -> '{suggestion['suggestedAction']}'")
            else:
                print("  ⚠️  AI did not provide a valid target selector")
                
        except Exception as e:
            print(f"  ⚠️  Could not adapt plan: {e}")
            import traceback
            traceback.print_exc()

    async def _verify_form_submission(self, step: dict, task_plan: dict):
        """Verify that a form submission was successful"""
        action = step.get("action")
        description = step.get("description", "").lower()
        
        # Check if this is a form submission step
        is_submit = (
            action == "click" and 
            ("create" in description or "submit" in description or "save" in description) and
            ("button" in description or "form" in description)
        )
        
        if is_submit:
            print("  🔍 Verifying form submission...")
            # Wait for modal to close and page to update
            await asyncio.sleep(2)
            
            # Check if modal is still open (it should be closed after successful submission)
            modal_open = await self.navigator.is_modal_open()
            if modal_open:
                print("  ⚠️  Modal still open - submission may have failed")
            else:
                print("  ✅ Modal closed - submission appears successful")
            
            # Wait a bit more for any list updates
            await asyncio.sleep(1)

    async def save_dataset(self, task_plan: dict):
        """Save captured states to organized dataset structure"""
        dataset_dir = Path("dataset") / task_plan["app"] / task_plan["taskName"]
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Save screenshots
        for i, state in enumerate(self.captured_states):
            filename = f"{str(i + 1).zfill(2)}-{state['name']}.png"
            dest_path = dataset_dir / filename
            
            shutil.copy2(state["path"], dest_path)
        
        # Save metadata
        metadata = {
            "task": self.current_task,
            "app": task_plan["app"],
            "taskName": task_plan["taskName"],
            "description": task_plan["description"],
            "capturedAt": datetime.now().isoformat(),
            "states": [
                {
                    "index": i + 1,
                    "name": s["name"],
                    "description": s["description"],
                    "timestamp": s["timestamp"]
                }
                for i, s in enumerate(self.captured_states)
            ]
        }
        
        metadata_path = dataset_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n💾 Dataset saved to: {dataset_dir}")

    def _filter_login_steps(self, plan: dict) -> dict:
        """Remove login-related steps from the plan since user is already logged in"""
        if not plan.get("steps"):
            return plan
        
        # Keywords that indicate login steps
        login_keywords = ["login", "sign in", "signin", "authenticate", "log in"]
        
        # Filter out login steps
        filtered_steps = []
        for step in plan["steps"]:
            description = step.get("description", "").lower()
            target = step.get("target", "").lower()
            action = step.get("action", "").lower()
            
            # Skip if it's a login step
            is_login_step = (
                any(keyword in description for keyword in login_keywords) or
                any(keyword in target for keyword in login_keywords) or
                (action == "click" and any(keyword in target for keyword in login_keywords))
            )
            
            if not is_login_step:
                filtered_steps.append(step)
            else:
                print(f"  🔄 Removed login step: {step.get('description')}")
        
        plan["steps"] = filtered_steps
        
        # Also fix startingUrl if it's a login page
        starting_url = plan.get("startingUrl", "").lower()
        if "login" in starting_url or "signin" in starting_url:
            # Change to app's main page based on app type
            app = plan.get("app", "").lower()
            if app == "linear":
                plan["startingUrl"] = "https://linear.app/projects"
            elif app == "notion":
                plan["startingUrl"] = "https://www.notion.so"
            else:
                # For other apps, try to infer main page from login URL
                plan["startingUrl"] = plan["startingUrl"].replace("/login", "").replace("/signin", "")
            print(f"  🔄 Changed startingUrl from login page to: {plan['startingUrl']}")
        
        return plan

