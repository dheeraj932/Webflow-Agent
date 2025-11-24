"""
Test file - Runs example workflows to demonstrate the system
"""

import asyncio
from dotenv import load_dotenv

from src.agent import AgentB

load_dotenv()


# Example tasks to test
TEST_TASKS = [
    {
        "name": "Linear - Create Project",
        "query": "How do I create a project in Linear?",
        "description": "Demonstrates creating a new project in Linear, capturing the project list, create button, modal, form, and success state."
    },
    {
        "name": "Linear - Filter Issues",
        "query": "How do I filter issues by status in Linear?",
        "description": "Shows how to filter issues, capturing the filter UI and filtered results."
    },
    {
        "name": "Notion - Filter Database",
        "query": "How do I filter a database in Notion?",
        "description": "Demonstrates filtering a Notion database, capturing the filter interface and results."
    },
    {
        "name": "Notion - Create Page",
        "query": "How do I create a new page in Notion?",
        "description": "Shows creating a new page, capturing the creation flow and new page state."
    }
]


async def run_tests():
    """Run all test tasks"""
    print("\n🧪 Starting UI State Capture Agent Tests\n")
    print("=" * 60)
    print(f"Running {len(TEST_TASKS)} test tasks...")
    print("=" * 60 + "\n")
    
    agent = AgentB()
    results = []
    
    for i, task in enumerate(TEST_TASKS):
        print(f"\n{'=' * 60}")
        print(f"Test {i + 1}/{len(TEST_TASKS)}: {task['name']}")
        print(f"Description: {task['description']}")
        print("=" * 60)
        
        try:
            result = await agent.execute_task(task["query"])
            results.append({
                **result,
                "testName": task["name"],
                "description": task["description"]
            })
            
            print(f"✅ Test {i + 1} completed successfully")
        except Exception as error:
            print(f"❌ Test {i + 1} failed: {error}")
            results.append({
                "testName": task["name"],
                "success": False,
                "error": str(error)
            })
        
        # Wait between tests
        if i < len(TEST_TASKS) - 1:
            print("\n⏳ Waiting 3 seconds before next test...\n")
            await asyncio.sleep(3)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    successful = sum(1 for r in results if r.get("success") is not False)
    failed = sum(1 for r in results if r.get("success") is False)
    
    print(f"Total Tests: {len(TEST_TASKS)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    print("\nDetailed Results:")
    for i, result in enumerate(results):
        print(f"\n{i + 1}. {result.get('testName', 'Unknown')}")
        if result.get("success") is not False:
            print(f"   ✅ Captured {result.get('capturedStates', 0)} states")
            print(f"   📁 Dataset: {result.get('datasetPath', 'N/A')}")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())

