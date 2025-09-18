"""Main FM Station Inspection Planner using LangGraph"""

import logging
from typing import Optional, Tuple
from langgraph.graph import StateGraph, START, END
from .agents import (
    FMStationState,
    language_processing_node,
    location_processing_node,
    database_query_node,
    route_planning_node,
    plan_evaluation_node,
    response_generation_node,
    location_based_planning_node,
    step_by_step_planning_node,
    multi_day_planning_node,
    detect_location_based_request,
    detect_step_by_step_request,
    should_continue_after_stations,
    check_for_errors,
    error_response_node
)
from ..config.config import Config
from ..services.location_choice_service import LocationChoiceService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FMStationPlanner:
    """Main orchestrator for FM station inspection planning using LangGraph"""

    def __init__(self):
        """Initialize the planner with LangGraph workflow"""

        # Build the LangGraph workflow
        self.workflow = self._build_workflow()

        logger.info("FM Station Planner initialized with LangGraph workflow")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create state graph
        workflow = StateGraph(FMStationState)

        # Add nodes
        workflow.add_node("language_processing", language_processing_node)
        workflow.add_node("location_processing", location_processing_node)
        workflow.add_node("database_query", database_query_node)
        workflow.add_node("route_planning", route_planning_node)
        workflow.add_node("plan_evaluation", plan_evaluation_node)
        workflow.add_node("response_generation", response_generation_node)
        workflow.add_node("location_based_planning", location_based_planning_node)
        workflow.add_node("step_by_step_planning", step_by_step_planning_node)
        workflow.add_node("multi_day_planning", multi_day_planning_node)
        workflow.add_node("error_response", error_response_node)

        # Add edges
        workflow.add_edge(START, "language_processing")

        # Conditional edge after language processing to detect request type
        workflow.add_conditional_edges(
            "language_processing",
            detect_step_by_step_request,
            {
                "multi_day": "multi_day_planning",
                "step_by_step": "step_by_step_planning",
                "standard": "location_processing"
            }
        )

        # Standard workflow path
        workflow.add_edge("location_processing", "database_query")

        # Conditional edge after database query
        workflow.add_conditional_edges(
            "database_query",
            should_continue_after_stations,
            {
                "routing": "route_planning",
                "response": "response_generation"
            }
        )

        # From route planning to plan evaluation
        workflow.add_edge("route_planning", "plan_evaluation")

        # From step-by-step planning to plan evaluation
        workflow.add_edge("step_by_step_planning", "plan_evaluation")

        # From plan evaluation to response generation
        workflow.add_edge("plan_evaluation", "response_generation")

        # All response paths end the workflow
        workflow.add_edge("response_generation", END)
        workflow.add_edge("location_based_planning", END)
        workflow.add_edge("multi_day_planning", END)
        workflow.add_edge("error_response", END)

        # Compile the workflow
        return workflow.compile()

    def plan_inspection(self,
                       user_input: str,
                       current_location: Optional[Tuple[float, float]] = None) -> str:
        """
        Main planning method using LangGraph workflow

        Args:
            user_input: Thai language input from user
            current_location: Optional current GPS coordinates (lat, lon)

        Returns:
            Thai language response with inspection plan
        """

        logger.info(f"Starting inspection planning for: {user_input}")

        try:
            # Initialize state
            initial_state: FMStationState = {
                "user_input": user_input,
                "requirements": {},
                "location_coords": {},
                "start_location": {},
                "stations": [],
                "route_info": {},
                "stations_ordered": [],
                "current_location": current_location,
                "location_based_plan": {},
                "plan_evaluation": {},
                "final_response": "",
                "errors": [],
                # New step-by-step fields
                "step_by_step_mode": False,
                "visited_station_ids": [],
                "current_step": 0,
                "nearest_station": None
            }

            # Override start location if provided
            if current_location:
                initial_state["start_location"] = {
                    "lat": current_location[0],
                    "lon": current_location[1],
                    "name": "Current Location"
                }

            # Execute the workflow
            result = self.workflow.invoke(initial_state)

            # Return the final response
            return result.get("final_response", "Sorry, an error occurred during processing")

        except Exception as e:
            logger.error(f"Error in LangGraph planning: {e}", exc_info=True)
            return f"Sorry, an error occurred during planning: {str(e)}"

    def plan_inspection_with_location(self,
                                    user_input: str,
                                    start_location: Tuple[float, float]) -> str:
        """
        Plan inspection with explicit start location (for mobile/Telegram bot)

        Args:
            user_input: User request text
            start_location: GPS coordinates (lat, lon)

        Returns:
            Thai language response with inspection plan
        """
        return self.plan_inspection(user_input, start_location)

    def get_workflow_visualization(self) -> bytes:
        """Get a visual representation of the LangGraph workflow"""
        try:
            return self.workflow.get_graph().draw_mermaid_png()
        except Exception as e:
            logger.error(f"Failed to generate workflow visualization: {e}")
            return None

class InteractivePlanner:
    """Interactive CLI for FM Station Planning"""

    def __init__(self):
        self.planner = FMStationPlanner()
        self.location_service = LocationChoiceService()

    def run(self):
        """Run interactive planning session"""
        print("=" * 60)
        print("FM Station Inspection Planner")
        print("=" * 60)
        print("Welcome to the FM Station Inspection Planning System")
        print("Type 'exit' or 'quit' to exit the program")
        print("-" * 60)

        while True:
            try:
                # Get user input
                user_input = input("\nPlease specify your requirements: ").strip()

                # Check for exit commands
                if user_input.lower() in ['exit', 'quit']:
                    print("\nThank you for using the service!")
                    break

                if not user_input:
                    print("Please specify your requirements")
                    continue

                # Ask for location choice if this is a planning request
                current_location = None
                if self.location_service.should_ask_location_choice(user_input):
                    print("\n" + self.location_service.get_location_choice_prompt())

                    # Get location choice
                    while current_location is None:
                        choice_input = input("\n📍 Your choice (1 or 2): ").strip()

                        if choice_input.lower() in ['exit', 'quit']:
                            print("\n👋 Thank you for using the service!")
                            return

                        choice = self.location_service.parse_location_choice(choice_input)

                        if choice['type'] == 'request_location':
                            print("\n📱 For console mode, I'll use NBTC23 base location instead.")
                            print("(In a real bot, you would share your GPS location)")
                            # Automatically use NBTC23 base for console mode
                            choice = self.location_service.parse_location_choice("2")

                        if choice['type'] in ['user_location', 'nbtc23_base']:
                            current_location = choice['coordinates']
                            print(f"\n✅ Location set: {choice['name']}")
                            break
                        else:
                            print(f"\n❓ {choice['description']}")
                else:
                    # Try to detect location automatically if available
                    try:
                        from ..utils.auto_location import AutoLocationDetector
                        location_detector = AutoLocationDetector()
                        current_location = location_detector.get_current_location()
                        if current_location:
                            location_info = location_detector.get_location_info()
                            print(f"✅ Auto-detected: {location_info}")
                    except ImportError:
                        pass

                # Process request
                print("\nProcessing...")
                response = self.planner.plan_inspection(user_input, current_location)

                # Display response
                print("\n" + "=" * 60)
                print("Inspection Plan:")
                print("-" * 60)
                print(response)
                print("=" * 60)

            except KeyboardInterrupt:
                print("\n\nThank you for using the service!")
                break
            except Exception as e:
                print(f"\nError occurred: {e}")
                print("Please try again")

if __name__ == "__main__":
    # Run interactive planner
    interactive = InteractivePlanner()
    interactive.run()