"""
FM Station Inspection Planner
Main entry point for the application using LangGraph
"""

from planner import FMStationPlanner, InteractivePlanner
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def example_usage():
    """Example usage of the FM Station Planner"""

    print("=" * 70)
    print("FM Station Inspection Planner with LangGraph - Example Usage")
    print("=" * 70)

    # Create planner instance
    planner = FMStationPlanner()

    # Example requests
    test_requests = [
        "Find 10 FM stations in Chaiyaphum province with inspection time 30-40 minutes and route planning",
        "Find 5 FM stations in Bangkok",
        "Need to inspect 8 stations in Khon Kaen within 2 hours",
        "Plan inspection route for 15 FM stations in Chiang Mai"
    ]

    for i, request in enumerate(test_requests, 1):
        print(f"\n{'='*70}")
        print(f"Example {i}: {request}")
        print("-" * 70)

        try:
            # Process request
            response = planner.plan_inspection(request)

            # Display response
            print(response)

        except Exception as e:
            print(f"Error: {e}")

        print("=" * 70)

        # Ask if user wants to continue
        if i < len(test_requests):
            cont = input("\nPress Enter to continue to next example (or 'q' to quit): ")
            if cont.lower() == 'q':
                break

def run_interactive():
    """Run interactive mode"""
    interactive = InteractivePlanner()
    interactive.run()

def main():
    """Main entry point"""

    print("=" * 70)
    print("FM Station Inspection Planner with LangGraph & OpenRouter")
    print("=" * 70)
    print("\nSelect mode:")
    print("1. Interactive mode (chat interface)")
    print("2. Example demonstrations")
    print("3. Exit")
    print("-" * 70)

    choice = input("Enter your choice (1/2/3): ").strip()

    if choice == "1":
        run_interactive()
    elif choice == "2":
        example_usage()
    elif choice == "3":
        print("Goodbye!")
        sys.exit(0)
    else:
        print("Invalid choice. Running interactive mode by default.")
        run_interactive()

if __name__ == "__main__":
    main()
