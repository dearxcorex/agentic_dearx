#!/usr/bin/env python
"""Test script to verify the fixes work"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.multi_day_planner import MultiDayPlanner

def test_parsing():
    """Test the improved parsing logic"""
    planner = MultiDayPlanner()

    # Test cases
    test_cases = [
        "give me a plan for inspection 20 station at Chaiyaphum and Nakorn Ratchasima in 2 day",
        "find 15 stations in cyp for 2 days",
        "plan 10 stations in nkr 1 day",
        "หา 12 สถานีในบุรีรัมย์ ไป 2 วัน"
    ]

    print("Testing parsing logic...")
    for test_case in test_cases:
        print(f"\nInput: {test_case}")
        result = planner._parse_multi_day_request(test_case)
        if result:
            print(f"Parsed: {result}")
        else:
            print("Failed to parse")

if __name__ == "__main__":
    test_parsing()