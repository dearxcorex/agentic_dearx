#!/usr/bin/env python
"""
Test script for the LangGraph-based FM Station Planner
"""

from planner import FMStationPlanner
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_planner():
    """Test the LangGraph FM Station Planner"""
    print("=== Testing LangGraph FM Station Planner ===")

    # Create planner instance
    try:
        planner = FMStationPlanner()
        print("[OK] Planner initialized successfully")
    except Exception as e:
        print(f"[FAIL] Failed to initialize planner: {e}")
        return False

    # Test simple planning request
    test_input = "Find 3 FM stations in Bangkok"

    try:
        print(f"\n[TEST] Testing with input: '{test_input}'")
        result = planner.plan_inspection(test_input)

        if result and isinstance(result, str):
            print("[OK] Planning completed successfully")
            print(f"\n[RESULT]\n{result}")
        else:
            print("[FAIL] Planning failed - no valid result returned")
            return False

    except Exception as e:
        print(f"[FAIL] Planning failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n=== Test completed ===")
    return True

if __name__ == "__main__":
    success = test_planner()
    exit(0 if success else 1)