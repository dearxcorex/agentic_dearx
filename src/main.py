#!/usr/bin/env python
"""
FM Station Inspection Planner - Main Entry Point

This is the main entry point for the FM Station Inspection Planner system.
It provides a command-line interface for planning multi-day FM station inspections.
"""

import sys
import os
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.planner import FMStationPlanner, InteractivePlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the FM Station Inspection Planner"""
    print("🎯 FM Station Inspection Planner")
    print("=" * 50)
    print("Multi-day planning with automatic home return by 17:00")
    print("Provinces: ชัยภูมิ (Chaiyaphum), นครราชสีมา (Nakhon Ratchasima), บุรีรัมย์ (Buriram)")
    print("=" * 50)
    print("\n📝 Example Requests:")
    print("• Thai: หา 10 สถานีในชัยภูมิ ไป 2 วัน")
    print("• English: find 15 stations in Chaiyaphum for 2 days")
    print("• Abbreviations: plan 8 stations in cyp for 1 day")
    print("• Mixed: give me a plan for 20 stations at nkr and cyp in 2 day")
    print("\n🔤 Province Codes:")
    print("• cyp = ชัยภูมิ (Chaiyaphum)")
    print("• nkr = นครราชสีมา (Nakhon Ratchasima)")
    print("• brr = บุรีรัมย์ (Buriram)")
    print("=" * 50)

    try:
        # Start interactive planner
        interactive = InteractivePlanner()
        interactive.run()
    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
    except Exception as e:
        logger.error(f"Error starting planner: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()