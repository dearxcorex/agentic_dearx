#!/usr/bin/env python
"""
FM Station Inspection Planner - Basic Usage Examples

This file demonstrates how to use the FM Station Inspection Planner
for various scenarios including single-day and multi-day planning.
"""

import sys
import os
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.planner import FMStationPlanner
from src.core.multi_day_planner import MultiDayPlanner

logging.basicConfig(level=logging.INFO)

def example_multi_day_planning():
    """Example: Multi-day planning with home return by 17:00"""
    print("=== Example: Multi-Day Planning ===")

    planner = FMStationPlanner()

    # Example request for 2-day trip
    user_input = "find me 10 stations in ชัยภูมิ i want to go 2 day make a plan for me"

    print(f"Request: {user_input}")
    print("\nProcessing...")

    result = planner.plan_inspection(user_input)

    print("Result:")
    print(result[:500] + "..." if len(result) > 500 else result)

def example_single_day_planning():
    """Example: Single day step-by-step planning"""
    print("\n=== Example: Single Day Planning ===")

    planner = FMStationPlanner()

    # Current location in Nakhon Ratchasima
    current_location = (14.938737322657747, 102.06082160579989)
    user_input = "make plan for 5 stations in นครราชสีมา for me"

    print(f"Request: {user_input}")
    print(f"Location: {current_location}")
    print("\nProcessing...")

    result = planner.plan_inspection(user_input, current_location)

    print("Result:")
    print(result[:400] + "..." if len(result) > 400 else result)

def example_direct_multi_day_planner():
    """Example: Using MultiDayPlanner directly"""
    print("\n=== Example: Direct MultiDayPlanner Usage ===")

    planner = MultiDayPlanner()

    user_input = "find me 6 stations in นครราชสีมา i want to go 1 day"

    print(f"Request: {user_input}")
    print("\nProcessing...")

    result = planner.plan_multi_day_inspection(user_input)

    print("Result:")
    print(result[:400] + "..." if len(result) > 400 else result)

def main():
    """Run all examples"""
    print("🎯 FM Station Inspection Planner - Usage Examples")
    print("=" * 60)

    try:
        # Run examples
        example_multi_day_planning()
        example_single_day_planning()
        example_direct_multi_day_planner()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("💡 Use src/main.py for interactive mode")

    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()