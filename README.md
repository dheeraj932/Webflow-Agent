# UI State Capture Agent System

An AI-powered multi-agent system that automatically navigates web applications and captures UI states based on natural language instructions.

## Overview

This system implements **Agent B**, which receives natural language questions from **Agent A** (e.g., "How do I create a project in Linear?") and automatically:
1. Navigates the live web application
2. Performs the requested task
3. Captures screenshots of each UI state in the workflow
4. Organizes the captured states by task

## Key Features

- **Generalizable**: Works across different web apps without hardcoding
- **Non-URL State Capture**: Captures modals, forms, and other UI states that don't have URLs
- **AI-Powered Navigation**: Uses LLM to understand tasks and plan navigation steps
- **Real-time Execution**: Interacts with live applications programmatically
- **Python Implementation**: Built with Python for easy extensibility

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── agent.py              # Agent B implementation
│   ├── navigator.py          # Web navigation logic
│   ├── screenshot.py        # Screenshot capture system
│   ├── config.py             # Configuration constants
│   └── logger.py             # Logging utility
├── dataset/                  # Captured UI states organized by task
├── screenshots/             # Temporary screenshot storage
├── requirements.txt
├── main.py                  # Main entry point
├── test.py                  # Test runner
└── README.md
```

## Setup

1. **Create Virtual Environment** (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chrome
   ```

3. **Configure Environment**
   Create a `.env` file in the root directory:
   ```bash
   echo "GROQ_API_KEY=your_groq_api_key_here" > .env
   ```
   Replace `your_groq_api_key_here` with your actual Groq API key from https://console.groq.com

4. **Run the Agent**
   ```bash
   python main.py "How do I create a project in Linear?"
   ```

## Usage

### Basic Usage

```python
from src.agent import AgentB

agent = AgentB()
result = await agent.execute_task("How do I create a project in Linear?")
```

### Example Tasks

The system supports various tasks across different apps:

**Linear:**
- "How do I create a project in Linear?"
- "How do I filter issues by status?"
- "How do I create a new issue?"

**Notion:**
- "How do I filter a database in Notion?"
- "How do I create a new page?"
- "How do I add a property to a database?"

## How It Works

1. **Task Understanding**: Agent B uses LLM to parse the natural language request and identify:
   - Target application
   - Action to perform
   - Key UI states to capture

2. **Navigation Planning**: The agent creates a step-by-step plan to:
   - Navigate to the starting URL
   - Find and interact with UI elements
   - Handle modals, forms, and other non-URL states

3. **Execution**: Using Playwright, the agent:
   - Opens Chrome browser
   - Navigates through the workflow
   - Captures screenshots at each significant UI state
   - Handles dynamic content and interactions

4. **State Capture**: Screenshots are captured when:
   - Navigating to a new URL
   - Opening/closing modals
   - Filling form fields
   - Completing actions
   - Reaching success states

## Dataset Structure

Captured UI states are organized in the `dataset/` directory:

```
dataset/
├── linear/
│   ├── create-project/
│   │   ├── 01-initial-state.png
│   │   ├── 02-create-button.png
│   │   ├── 03-modal-open.png
│   │   ├── 04-form-filled.png
│   │   ├── 05-success.png
│   │   └── metadata.json
│   └── filter-issues/
│       └── ...
└── notion/
    └── ...
```

## Technical Approach

### Generalization Strategy

1. **Semantic Element Finding**: Uses AI to understand UI elements semantically rather than hardcoding selectors
2. **Pattern Recognition**: Identifies common UI patterns (buttons, forms, modals) across different apps
3. **Adaptive Navigation**: Adjusts navigation strategy based on the application structure

### Non-URL State Handling

- **Modal Detection**: Identifies and captures modal states
- **Form State Tracking**: Captures form states before and after interactions
- **Dynamic Content**: Handles dynamically loaded content and single-page applications

## Testing

Run example workflows:

```bash
python test.py
```

This will execute predefined test tasks and capture their UI states.

## Features

- **Automatic Error Recovery**: AI-powered error handling that automatically fixes selectors and retries failed steps
- **Smart Element Detection**: Intelligent matching of UI elements using multiple strategies (text, aria-label, context)
- **Persistent Login**: Remembers login state across sessions
- **Contenteditable Support**: Handles modern rich text editors (ProseMirror, etc.)
- **Custom Dropdown Support**: Works with custom dropdown components, not just standard HTML selects

## Requirements

- Python 3.8+
- Chrome browser (installed via Playwright)
- Groq API key (get one at https://console.groq.com)

## License

MIT
