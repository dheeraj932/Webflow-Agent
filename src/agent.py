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
                
                # Step 2.5: Always prompt for manual login
                print("\n" + "=" * 60)
                print("⏸️  PAUSED: Please log in manually in the browser")
                print("=" * 60)
                input("Press ENTER after you have logged in to continue...\n")
                
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
        prompt = f"""
You are Agent B in a multi-agent system. Agent A sends you natural-language task requests such as:
- “How do I create a project in Linear?”
- “How do I filter a database in Notion?”
- “How do I change workspace settings in Asana?”
- Or any similar task in any other web app.

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
   You may encounter Linear, Notion, Asana, Trello, Jira, Monday.com, custom in-house tools, or completely unknown apps.
   Therefore:
   - Infer UI layouts and navigation structures.
   - Infer meaning from visible text, labels, roles, ARIA attributes.
   - Never assume app-specific naming or fixed locations for UI elements.

2. **Generalize Across Any Task**
   Tasks may involve:
   - Create / Add / New
   - Edit / Update
   - Delete / Archive
   - Filter / Search / Sort
   - Navigate between sections
   - Change workspace settings
   - Duplicate / Move / Assign
   Infer workflow based on task semantics and visible UI.

3. **Capture UI States Even Without URLs**
   Many states have no unique URL:
   - Modals
   - Drawers
   - Panels
   - Inline editors
   - Dropdowns
   Capture states before/after interactions when meaningful.

4. **CRITICAL: Discover Before Navigating**
   **ALWAYS discover elements on the current page before navigating.**
   - Start at the startingUrl (usually the app's main page)
   - Use a "discover" action to see what navigation options are available
   - Use "find" to locate navigation elements (e.g., section names relevant to the task such as "Projects", "Issues", "Dashboard", "Settings"—these are examples only, actual labels must come from discover)
   - Click on navigation elements to navigate, NOT by using direct URLs
   - Only use "navigate" action for the initial startingUrl, never for internal navigation

5. **Use "navigate" ONLY for Initial Starting URL**
   **IMPORTANT:** Only use "navigate" for the very first URL (startingUrl).
   Example:
   "navigate": "https://app.example.com"  ✅ (only for startingUrl)
   "navigate": "https://app.example.com/projects"  ❌ (WRONG - use discover + click instead)
   
   For all internal navigation within the app:
   - First use "discover" to see available navigation options
   - Then use "find" to locate the navigation element (e.g., section names relevant to the task such as "Projects", "Issues", "Tasks", "Board"—these are examples only, actual labels must come from discover)
   - Finally use "click" to navigate to that section

6. **Use "click" for ALL Navigation and UI Elements**
   Examples:
   - "target": "text=Projects" (for navigating to a Projects section)
   - "target": "text=Add project" (for creating new items)
   - "target": "role=button[name='New']"
   - "target": "aria-label=Create task"
   
   **Remember:** Navigation within the app = discover → find → click, NOT navigate with URLs.

7. **Always Use Wait Steps**
   Wait 2–3 seconds (or equivalent explicit "wait" step) after:
   - Modal opens
   - Form submission
   - Navigation change

8. **Use Realistic Input Text**
   Examples:
   - "Sample Project"
   - "Demo Task"
   - "Research Database"

9. **CRITICAL: Always Type Into Fields When Task Requires It**
   **If the task mentions filling in a field (title, description, name, etc.), you MUST include a "type" action step.**
   
   Examples:
   - Task: "Create an issue with title 'Bug Fix'"
     ✅ REQUIRED: {{"action": "type", "target": "Title", "value": "Bug Fix"}}
     ❌ WRONG: {{"action": "find", "target": "Title"}} (finding is not enough!)
   
   - Task: "Add description 'This is a test'"
     ✅ REQUIRED: {{"action": "type", "target": "Description", "value": "This is a test"}}
     ❌ WRONG: {{"action": "find", "target": "Description"}} (finding is not enough!)
   
   **Rule:** If the user provides specific text to enter (title, description, name, etc.), you MUST use the "type" action with that exact text. Finding the field is optional - typing is mandatory.

10. **Do NOT Include Login Steps**
   The user is already logged in.

=====================================================================
📌 SECTION 2 — DYNAMIC EXPLORATION & FALLBACKS
=====================================================================

**MANDATORY WORKFLOW FOR NAVIGATION:**
1. Start at startingUrl (use "navigate" only here)
2. Use "discover" to see all available navigation options
3. Use "find" to locate the target navigation element (e.g., section names relevant to the task such as "Projects", "Issues", "Tasks", "Settings"—these are examples only, actual labels come from discover)
4. Use "click" to navigate to that section
5. Continue with task-specific actions

**NEVER use "navigate" with internal URLs like "/projects" or "/issues".**
**ALWAYS discover and click navigation elements instead.**

Allowed exploration actions:

- **"discover"**  
  **MANDATORY FIRST STEP** after landing on startingUrl.
  Lists visible:
  - buttons, links, menus
  - headings, sidebar items
  - modal indicators
  - navigation elements
  
  Use this to understand what navigation options are available before clicking.

- **"find"**  
  Semantic matching for:
  - Navigation elements: section names relevant to the task (e.g., "Projects", "Issues", "Dashboard", "Tasks", "Settings"—these are examples only, actual labels depend on the app's UI)
  - Action buttons: "Create" ~ "Add" ~ "New" ~ "+"
  - Filter/search elements
  
  Use this to locate specific elements before clicking them.

- **"extractText"**  
  Reads visible text to infer:
  - current location
  - modal presence
  - visible lists
  - available actions

- **"conditional"**  
  Execute steps only if some element or state exists.

Fallback rules:
- If a target navigation label is not found, try semantically related alternatives based on the task (e.g., sections representing collections, lists, dashboards, or content areas). The exact labels depend on the app's UI.
- If an action button label (e.g., "Create") isn't found → try semantically related alternatives (e.g., "Add", "New", "+", or synonyms implied by the task context).
- If element not clickable → try clicking a parent or wrapper element.
- If a modal doesn't open → retry after a delay and re-discover.

=====================================================================
📌 SECTION 2.5 — MANDATORY UI LABEL VALIDATION (CRITICAL)
=====================================================================

Before clicking ANY button or actionable element, Agent B MUST:

1. Perform a "discover" step to list visible UI elements.
2. Use "extractText" to gather ALL visible button/link labels.
3. Perform semantic matching between:
   - the task intent (e.g., “create project”), and
   - visible UI labels (e.g., “Add project”, “New project”, “+ Project”, “Create”, “New item”).
4. Select the MOST semantically relevant visible label.
5. Use ONLY the real UI label in "target".
6. NEVER assume a button label from the task description.
7. Only click labels confirmed to exist on screen.

Example:
If the visible button is **“Add project”**, you MUST output:
"target": "text=Add project"
NOT:
"target": "text=Create project"

This rule applies to ALL apps and ALL tasks.

=====================================================================
📌 SECTION 3 — TASK INTERPRETATION LOGIC
=====================================================================

Before generating steps, Agent B MUST:
1. Parse the natural-language request.
2. Identify task intent (create, filter, navigate, delete, configure, etc.).
3. Identify target object (project, task, page, database, issue, workspace, etc.).
4. Identify the app (from the task text, e.g., "in Linear", "in Notion", "in Asana", or infer if possible).
5. Determine a reasonable **startingUrl**:
   - Use the main application URL inferred from the app name and task (e.g., "https://linear.app", "https://www.notion.so", "https://app.asana.com", or another appropriate base URL).
   - If app is unknown, choose a reasonable HTTPS base URL based on its name (e.g., "https://{{appNameLower}}.com" or "https://app.{{appNameLower}}.com") and specify it in "startingUrl".
6. Build a logical workflow:
   - Navigate to startingUrl (ONLY use "navigate" here)
   - Discover visible elements (MANDATORY first step)
   - Find navigation element (e.g., section names relevant to the task such as "Projects", "Issues", "Tasks", "Settings"—these are examples only, actual labels must come from discover)
   - Click navigation element to navigate (NEVER use "navigate" with internal URLs)
   - Discover visible elements on new page
   - Validate UI labels via "discover" + "extractText"
   - Open modal/form if needed
   - **CRITICAL: For EACH input field mentioned in the task, you MUST:**
     * Find the field (optional, can skip explicit find if obvious)
     * TYPE into the field using "type" action with the actual value from the task
   - **CRITICAL: For dropdown/select fields:**
     * Use "select" action with target = field name (e.g., "Priority", "Status", "Assignee")
     * Use value = the option to select (e.g., "Medium", "High", "Low")
     * Example: {{"action": "select", "target": "Priority", "value": "Medium"}}
     * ❌ WRONG: {{"action": "select", "target": "text=Medium", "value": ""}}
     * ✅ CORRECT: {{"action": "select", "target": "Priority", "value": "Medium"}}
   - **CRITICAL: Only include steps that are EXPLICITLY mentioned in the task**
     * If the task doesn't mention assigning, assigning to a user, or an assignee field → DO NOT include an "Assignee" step
     * If the task doesn't mention a status, priority, or label → DO NOT include those steps
     * Only add steps for fields/actions that are explicitly requested in the task description
     * Example: Task says "assign it as medium priority" → include Priority step ✅
     * Example: Task says "create an issue with title X" → DO NOT add Assignee step ❌
   - Submit the form
   - Verify success
   
   **IMPORTANT:** 
   - If the task asks you to fill in a title, description, or any text field, you MUST include a "type" action step. Finding the field is NOT enough - you must actually type the value.
   - For dropdowns, the "target" must be the FIELD NAME (like "Priority"), not the option value (like "Medium"). The "value" is the option to select.
   - **NEVER add optional steps that aren't mentioned in the task** (e.g., don't add "Assignee" if task doesn't mention assignment)

=====================================================================
📌 SECTION 4 — JSON OUTPUT FORMAT
=====================================================================

Your result must be JSON like:
```json
{{
  "app": "linear" | "notion" | "asana" | "other",
  "taskName": "short-task-name",
  "description": "brief overview",
  "startingUrl": "https://<main-app-url>",
  "steps": [
    {{
      "description": "What this step does",
      "action": "navigate" | "click" | "type" | "wait" | "select" |
                "discover" | "find" | "extractText" | "conditional",
      "target": "selector or field name (for select: use field name like 'Priority', not option value)",
      "value": "text typed (for type) or option to select (for select, e.g., 'Medium', 'High')",
      "captureBefore": true/false,
      "captureAfter": true/false
    }}
  ]
}}
=====================================================================
📌 SECTION 5 — IMPORTANT URL RULES

CRITICAL: Only use URLs for startingUrl, never for internal navigation!

Determining startingUrl:

Infer the main application URL from the app name in the task.

Examples (not hard rules, just illustrations):

Linear → "https://linear.app
"

Notion → "https://www.notion.so
"

Asana → "https://app.asana.com
"

Generic app "Foobar" → "https://foobar.com
" or "https://app.foobar.com
"

Usage rules:

Use "navigate" only once, to the startingUrl.

For all internal navigation:

Do NOT use "navigate" to URLs like "/projects", "/issues", "/settings", etc. ❌

INSTEAD: use the pattern: discover → find navigation element → click ✅

Do NOT navigate to login URLs. Assume the user is already authenticated.

=====================================================================
📌 SECTION 6 — REQUIRED VERIFICATION STEPS

After submissions or UI transitions:

Use a "wait" step (2–3 seconds or until a condition is met).

Verify modal closed if you submitted a modal form.

Verify new item appears in the relevant list or view.

Capture updated state with "captureAfter": true on the relevant step(s).

=====================================================================
📌 SECTION 7 — EXAMPLE WORKFLOW (GENERIC PATTERN)

Example workflow for: "How do I create a project in a project-management app?"
{{
  "app": "other",
  "taskName": "create-project",
  "startingUrl": "https://app.example.com",
  "steps": [
    {{
      "description": "Navigate to the app main page",
      "action": "navigate",
      "target": "https://app.example.com",
      "captureAfter": true
    }},
    {{
      "description": "Discover available navigation options on the main page",
      "action": "discover",
      "captureAfter": true
    }},
    {{
      "description": "Extract visible text to understand available sections (e.g., section names relevant to the task such as Projects, Tasks, Boards—these are examples only)",
      "action": "extractText",
      "captureAfter": true
    }},
    {{
      "description": "Find the navigation element that best matches a projects-like area (e.g., section names relevant to the task such as 'Projects', 'Boards', 'Tasks', 'Workspaces'—these are examples only)",
      "action": "find",
      "target": "Projects",
      "captureAfter": true
    }},
    {{
      "description": "Click the chosen navigation element to move into the projects area",
      "action": "click",
      "target": "text=Projects",
      "captureAfter": true
    }},
    {{
      "description": "Discover elements on the projects area page",
      "action": "discover",
      "captureAfter": true
    }},
    {{
      "description": "Extract visible text to identify the most relevant create/add button for new projects",
      "action": "extractText",
      "captureAfter": true
    }},
    {{
      "description": "Find a button or control that semantically matches creating a new project (e.g., 'New project', 'Add project', 'Create', '+')",
      "action": "find",
      "target": "Create",
      "captureAfter": true
    }},
    {{
      "description": "Click the identified button to open the create-project modal or form",
      "action": "click",
      "target": "text=Create",
      "captureAfter": true
    }},
    {{
      "description": "Wait for the modal or creation form to be fully visible",
      "action": "wait",
      "target": "[role=\\"dialog\\"]",
      "captureAfter": true
    }},
    {{
      "description": "Type the project name into the name/title field",
      "action": "type",
      "target": "Name",
      "value": "Sample Project",
      "captureAfter": true
    }},
    {{
      "description": "If needed, fill out any optional description or other required fields",
      "action": "conditional",
      "target": "Fill additional fields if required",
      "captureBefore": true,
      "captureAfter": true
    }},
    {{
      "description": "Click the primary button that submits the project creation (e.g., 'Create project', 'Add', 'Save')",
      "action": "click",
      "target": "text=Create project",
      "captureBefore": true,
      "captureAfter": true
    }},
    {{
      "description": "Wait for the operation to complete and the project to appear in the list",
      "action": "wait",
      "target": "list-refresh",
      "captureAfter": true
    }}
  ]
}}
Example workflow for: "Create an issue with title 'Bug Fix' and description 'Fix the bug'" (generic issue-tracking app):
{{
  "app": "other",
  "taskName": "create-issue",
  "startingUrl": "https://issues.example.com",
  "steps": [
    {{
      "description": "Navigate to the main page of the issue-tracking app",
      "action": "navigate",
      "target": "https://issues.example.com",
      "captureAfter": true
    }},
    {{
      "description": "Discover navigation options on the landing page",
      "action": "discover",
      "captureAfter": true
    }},
    {{
      "description": "Extract text to identify an issues or tickets section",
      "action": "extractText",
      "captureAfter": true
    }},
    {{
      "description": "Click the navigation element that best matches the issues area (e.g., 'Issues', 'Bugs', 'Tickets')",
      "action": "click",
      "target": "text=Issues",
      "captureAfter": true
    }},
    {{
      "description": "Discover elements in the issues area",
      "action": "discover",
      "captureAfter": true
    }},
    {{
      "description": "Find the button or control to create a new issue",
      "action": "find",
      "target": "New issue",
      "captureAfter": true
    }},
    {{
      "description": "Click the control to open the new-issue form",
      "action": "click",
      "target": "text=New issue",
      "captureAfter": true
    }},
    {{
      "description": "Type the provided title into the title field",
      "action": "type",
      "target": "Title",
      "value": "Bug Fix",
      "captureAfter": true
    }},
    {{
      "description": "Type the provided description into the description field",
      "action": "type",
      "target": "Description",
      "value": "Fix the bug",
      "captureAfter": true
    }},
    {{
      "description": "Select Medium priority from Priority dropdown",
      "action": "select",
      "target": "Priority",
      "value": "Medium",
      "captureAfter": true
    }},
    {{
      "description": "Submit the new issue using the primary submit button (e.g., 'Create issue', 'Save')",
      "action": "click",
      "target": "text=Create issue",
      "captureBefore": true,
      "captureAfter": true
    }},
    {{
      "description": "Wait briefly and verify that the new issue appears in the list",
      "action": "wait",
      "target": "state-change-indicator",
      "captureAfter": true
    }}
  ]
}}

**CRITICAL DISCLAIMER:**
These examples illustrate the pattern only. Actual labels, field names, and selectors MUST always come from discover + extractText, not from these examples. This ensures the model never treats examples as truth. The examples show the workflow structure, but all specific UI elements must be discovered from the live page.

=====================================================================
📌 SECTION 8 — WHAT YOU MUST RETURN

Your final JSON MUST:
✔ Use "navigate" ONLY for startingUrl
✔ Use "discover" as first step after startingUrl
✔ Use "find" + "click" for ALL internal navigation
✔ For EVERY field that needs to be filled (title, description, name, etc.), include a "type" action with the actual value
✔ Include exploration via "discover", "find", and "extractText"
✔ Include UI label validation based on real visible text
✔ Use the REAL UI text for buttons in "target"
✔ Include captures (captureBefore / captureAfter) around meaningful state changes
✔ Include waits for navigation, modal open, and submissions
✔ Handle non-URL states (modals, drawers, inline editors, etc.)
✔ Work across ANY app (known or unknown)
✔ Exclude login steps
✔ Apply deep reasoning and semantic matching between task and UI

=====================================================================
📌 END OF SYSTEM PROMPT

When ready, analyze the following task query:

Task: "{task_query}"
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
            
            # Remove steps that aren't mentioned in the task (like optional assignee steps)
            plan = self._filter_unmentioned_steps(plan, task_query)
            
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
        elif action == "discover":
            await self.navigator.discover()
        elif action == "find":
            await self.navigator.find(target)
        elif action == "extractText":
            await self.navigator.extract_text()
        elif action == "skip":
            print(f"  ⏭️  Skipping step: {step.get('description', 'No description')}")
            return  # Skip this step
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

**CRITICAL RULES - THESE ARE ABSOLUTE:**
1. The suggested selector MUST semantically match the original target. For example:
   - If target is "Assignee" → selector MUST match fields related to assignment/user assignment ONLY
   - If target is "Title" → selector MUST match title/name fields ONLY, NEVER description, assignee, or other fields
   - If target is "Description" → selector MUST match description/body fields ONLY, NEVER title, assignee, or other fields
2. If no element semantically matches the target, you MUST respond with "skip": true instead of suggesting ANY field
3. DO NOT suggest a different field type - this will cause data corruption:
   - ❌ NEVER suggest "Title" field when looking for "Assignee"
   - ❌ NEVER suggest "Description" field when looking for "Title"
   - ❌ NEVER suggest "Title" field when looking for "Description"
   - ❌ NEVER suggest any field that doesn't exactly match the semantic meaning of the target
4. If you cannot find a matching field, set "skip": true and explain why in "reason"

Respond with JSON:
{{
  "suggestedAction": "{action}",
  "target": "the correct selector (e.g., text=ButtonName, [aria-label='Label'], #id, etc.) OR null if no match found",
  "reason": "explanation of why this selector matches the intended target, or why no match was found",
  "confidence": "high" | "medium" | "low",
  "skip": true/false (set to true if the field doesn't exist and the step should be skipped)
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
            
            # Check if step should be skipped
            if suggestion.get("skip", False):
                print(f"  ⏭️  Step should be skipped - field doesn't exist or isn't needed")
                # Mark step to be skipped by changing action to a no-op
                task_plan["steps"][failed_step_index]["action"] = "skip"
                task_plan["steps"][failed_step_index]["target"] = "step-skipped"
                return
            
            # Validate that suggested target semantically matches original target
            original_target_lower = target.lower().strip()
            suggested_target = suggestion.get("target", "").strip()
            
            if suggested_target:
                suggested_lower = suggested_target.lower()
                
                # STRICT VALIDATION: Check for explicit mismatches first
                # These are known wrong field mappings that should NEVER happen
                explicit_mismatches = [
                    ("assignee", "title"),
                    ("assignee", "name"),
                    ("assignee", "description"),
                    ("title", "description"),
                    ("title", "assignee"),
                    ("description", "title"),
                    ("description", "assignee"),
                ]
                
                for original, wrong_field in explicit_mismatches:
                    if original in original_target_lower and wrong_field in suggested_lower:
                        print(f"  ❌ ERROR: Cannot use '{wrong_field}' field for '{original}' target - these are different fields!")
                        print(f"  ⏭️  Skipping this step to prevent data corruption")
                        task_plan["steps"][failed_step_index]["action"] = "skip"
                        task_plan["steps"][failed_step_index]["target"] = "step-skipped"
                        return
                
                # Check if suggested target semantically matches original
                # Extract key words from original target
                original_keywords = set(word for word in original_target_lower.split() if len(word) > 2)
                
                # Check for semantic matches
                matches_semantically = False
                
                # Exact match or contains original keywords
                if original_target_lower in suggested_lower or suggested_lower in original_target_lower:
                    matches_semantically = True
                # Check for keyword matches
                elif any(keyword in suggested_lower for keyword in original_keywords if len(keyword) > 2):
                    matches_semantically = True
                # Check for common semantic relationships (only positive matches)
                elif (original_target_lower == "assignee" and ("assign" in suggested_lower or "user" in suggested_lower or "owner" in suggested_lower)):
                    matches_semantically = True
                elif (original_target_lower == "title" and ("title" in suggested_lower or ("name" in suggested_lower and "issue" in suggested_lower))):
                    matches_semantically = True
                elif (original_target_lower == "description" and ("description" in suggested_lower or "body" in suggested_lower or "content" in suggested_lower)):
                    matches_semantically = True
                
                if not matches_semantically:
                    print(f"  ⚠️  Warning: Suggested selector '{suggested_target}' doesn't semantically match original target '{target}'")
                    print(f"  ⏭️  Skipping this step instead of using wrong field")
                    task_plan["steps"][failed_step_index]["action"] = "skip"
                    task_plan["steps"][failed_step_index]["target"] = "step-skipped"
                    return
                
                # Update the failed step with the suggestion
                old_target = task_plan["steps"][failed_step_index]["target"]
                task_plan["steps"][failed_step_index]["target"] = suggested_target
                print(f"  🔄 Updated selector: '{old_target}' -> '{suggested_target}'")
                
                # If action needs to change, update it
                if suggestion.get("suggestedAction") and suggestion["suggestedAction"] != action:
                    task_plan["steps"][failed_step_index]["action"] = suggestion["suggestedAction"]
                    print(f"  🔄 Updated action: '{action}' -> '{suggestion['suggestedAction']}'")
            else:
                print("  ⚠️  AI did not provide a valid target selector - skipping step")
                task_plan["steps"][failed_step_index]["action"] = "skip"
                task_plan["steps"][failed_step_index]["target"] = "step-skipped"
                
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
    
    def _filter_unmentioned_steps(self, plan: dict, task_query: str) -> dict:
        """Remove steps that aren't explicitly mentioned in the task query"""
        if not plan.get("steps"):
            return plan
        
        task_lower = task_query.lower()
        filtered_steps = []
        
        # Keywords that indicate optional steps that shouldn't be included unless mentioned
        # Note: "assign" can mean "assign priority" (priority) or "assign to user" (assignee)
        # We need to distinguish between these contexts
        optional_step_keywords = {
            "assignee": ["assignee", "assign to", "assigned to", "user assignment", "assigning to", "assign to user", "assign to a user"],
            "status": ["status", "set status", "change status"],
            "label": ["label", "labels", "add label", "tag"],
            "due date": ["due date", "due", "deadline"],
            "milestone": ["milestone"],
        }
        
        # Check if task mentions user assignment (not priority assignment)
        # "assign it as priority" or "assign priority" = priority, NOT assignee
        # "assign to user" or "assign to" = assignee
        task_mentions_user_assignment = any(
            phrase in task_lower for phrase in [
                "assign to", "assign to a", "assign to user", "assign to me", 
                "assignee", "assigned to", "user assignment"
            ]
        ) and not any(
            phrase in task_lower for phrase in [
                "assign it as", "assign as", "assign priority", "assign status"
            ]
        )
        
        for step in plan["steps"]:
            description = step.get("description", "").lower()
            target = step.get("target", "").lower()
            action = step.get("action", "").lower()
            value = step.get("value", "").lower()
            
            # Check if this step is about an optional field
            should_include = True
            
            # Special handling for assignee - check if it's about user assignment, not priority
            if "assignee" in description or "assignee" in target or "assignee" in value:
                # Check if step is about assigning to a user (not priority)
                is_user_assignment_step = (
                    "assignee" in description or
                    "assignee" in target or
                    "assignee" in value or
                    ("assign" in description and "user" in description) or
                    ("assign" in target and "user" in target) or
                    ("assign" in value and "user" in value)
                )
                
                if is_user_assignment_step and not task_mentions_user_assignment:
                    print(f"  🔄 Removed unmentioned step: {step.get('description')} (task doesn't mention user assignment)")
                    should_include = False
                    continue
            
            # Check other optional fields
            for field_name, keywords in optional_step_keywords.items():
                if field_name == "assignee":
                    continue  # Already handled above
                
                # Check if step is about this optional field (check description, target, and value)
                is_about_field = (
                    field_name in description or
                    field_name in target or
                    field_name in value or
                    any(keyword in description for keyword in keywords) or
                    any(keyword in target for keyword in keywords) or
                    any(keyword in value for keyword in keywords)
                )
                
                # Check if task mentions this field
                task_mentions_field = any(keyword in task_lower for keyword in keywords)
                
                if is_about_field and not task_mentions_field:
                    print(f"  🔄 Removed unmentioned step: {step.get('description')} (task doesn't mention {field_name})")
                    should_include = False
                    break
            
            if should_include:
                filtered_steps.append(step)
        
        plan["steps"] = filtered_steps
        return plan

