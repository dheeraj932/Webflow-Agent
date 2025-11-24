"""
Main entry point for UI State Capture Agent System
Agent B - Receives tasks and captures UI states
"""

import asyncio
import sys
from dotenv import load_dotenv

from src.agent import AgentB

load_dotenv()


async def main():
    """Main function to run the agent"""
    agent = AgentB()
    
    # Get task from command line arguments or use default
    task_query = sys.argv[1] if len(sys.argv) > 1 else "How do I create a project in Linear?"
    
    try:
        result = await agent.execute_task(task_query)
        
        print("\n" + "=" * 60)
        print("📊 Task Execution Summary")
        print("=" * 60)
        print(f"Task: {result['task']}")
        print(f"App: {result['plan']['app']}")
        print(f"Captured States: {result['capturedStates']}")
        print(f"Dataset Path: {result['datasetPath']}")
        print("=" * 60 + "\n")
        
    except Exception as error:
        print(f"\n❌ Task execution failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

