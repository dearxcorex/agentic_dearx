#!/usr/bin/env python3
"""
FM Station Inspection Bot Interface
Handles user interaction with location choice functionality
"""

import sys
import os
from typing import Dict, Optional, Tuple, Any
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.planner import FMStationPlanner
from src.services.location_choice_service import LocationChoiceService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FMStationBot:
    """Bot interface for FM Station Inspection planning with location choice"""

    def __init__(self):
        self.planner = FMStationPlanner()
        self.location_service = LocationChoiceService()
        self.user_sessions = {}  # Track user sessions

    def process_message(self,
                       user_id: str,
                       message: str,
                       user_location: Optional[Tuple[float, float]] = None) -> str:
        """
        Process user message and return appropriate response

        Args:
            user_id: Unique user identifier
            message: User's message
            user_location: Optional GPS coordinates from user

        Returns:
            Bot response message
        """
        try:
            # Initialize user session if needed
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {
                    'state': 'initial',
                    'location_choice': None,
                    'pending_request': None
                }

            session = self.user_sessions[user_id]

            # Handle different conversation states
            if session['state'] == 'initial':
                return self._handle_initial_message(user_id, message, user_location)

            elif session['state'] == 'waiting_location_choice':
                return self._handle_location_choice(user_id, message, user_location)

            elif session['state'] == 'waiting_gps_location':
                return self._handle_gps_location(user_id, message, user_location)

            elif session['state'] == 'ready_for_planning':
                return self._handle_planning_request(user_id, message, user_location)

            elif session['state'] == 'waiting_shortfall_response':
                return self._handle_shortfall_response(user_id, message, user_location)

            else:
                # Reset session on unknown state
                session['state'] = 'initial'
                return self._handle_initial_message(user_id, message, user_location)

        except Exception as e:
            logger.error(f"Error processing message for user {user_id}: {e}")
            return f"❌ Sorry, an error occurred: {str(e)}\n\nPlease try again or type 'help' for assistance."

    def _handle_initial_message(self,
                               user_id: str,
                               message: str,
                               user_location: Optional[Tuple[float, float]]) -> str:
        """Handle initial user message"""
        session = self.user_sessions[user_id]

        # Check if user is asking for help
        if message.lower().strip() in ['help', 'start', '/start', '/help']:
            return self._get_help_message()

        # Check if this looks like a planning request
        if self.location_service.should_ask_location_choice(message):
            # Store the planning request
            session['pending_request'] = message
            session['state'] = 'waiting_location_choice'
            return self.location_service.get_location_choice_prompt(user_id)

        # If user shared location directly, ask if they want to use it
        if user_location:
            session['pending_request'] = message
            session['state'] = 'waiting_location_choice'
            choice = self.location_service.parse_location_choice("1", user_location, user_id)
            return (self.location_service.get_location_confirmation(choice) +
                   f"\n\nNow processing your request: '{message}'...")

        # General greeting or unclear message
        return self._get_welcome_message()

    def _handle_location_choice(self,
                               user_id: str,
                               message: str,
                               user_location: Optional[Tuple[float, float]]) -> str:
        """Handle location choice selection"""
        session = self.user_sessions[user_id]

        choice = self.location_service.parse_location_choice(message, user_location, user_id)

        if choice['type'] == 'request_location':
            session['state'] = 'waiting_gps_location'
            return choice['description'] + "\n\n" + self.location_service.get_location_confirmation(choice)

        elif choice['type'] in ['user_location', 'nbtc23_base']:
            session['location_choice'] = choice
            session['state'] = 'ready_for_planning'

            # Process the pending request immediately
            if session.get('pending_request'):
                planning_result = self._execute_planning(
                    session['pending_request'],
                    choice['coordinates'],
                    user_id
                )
                session['pending_request'] = None
                return (self.location_service.get_location_confirmation(choice) +
                       f"\n\n{planning_result}")
            else:
                return (self.location_service.get_location_confirmation(choice) +
                       "\n\nYou can now request inspection plans!")

        else:  # unclear choice
            return choice['description']

    def _handle_gps_location(self,
                            user_id: str,
                            message: str,
                            user_location: Optional[Tuple[float, float]]) -> str:
        """Handle GPS location sharing"""
        session = self.user_sessions[user_id]

        if user_location:
            choice = self.location_service.parse_location_choice("1", user_location, user_id)
            session['location_choice'] = choice
            session['state'] = 'ready_for_planning'

            # Process pending request if exists
            if session.get('pending_request'):
                planning_result = self._execute_planning(
                    session['pending_request'],
                    choice['coordinates'],
                    user_id
                )
                session['pending_request'] = None
                return (self.location_service.get_location_confirmation(choice) +
                       f"\n\n{planning_result}")
            else:
                return (self.location_service.get_location_confirmation(choice) +
                       "\n\nYou can now request inspection plans!")
        else:
            return ("📱 Please share your GPS location using the location button, " +
                   "or type '2' to use NBTC23 base location instead.")

    def _handle_planning_request(self,
                                user_id: str,
                                message: str,
                                user_location: Optional[Tuple[float, float]]) -> str:
        """Handle planning request when location is already set"""
        session = self.user_sessions[user_id]

        # Check if user wants to change location
        if message.lower().strip() in ['change location', 'new location', 'reset location']:
            session['state'] = 'waiting_location_choice'
            session['location_choice'] = None
            return self.location_service.get_location_choice_prompt(user_id)

        # Check if this is a planning request
        if self.location_service.should_ask_location_choice(message):
            return self._execute_planning(message, session['location_choice']['coordinates'], user_id)

        # Handle other commands
        if message.lower().strip() in ['help', '/help']:
            return self._get_help_message()

        # For unclear messages, provide guidance
        return ("💡 **Ready for Planning!**\n\n" +
               f"Current location: {session['location_choice']['name']}\n\n" +
               "You can now request inspection plans like:\n" +
               "• 'find 10 stations in ชัยภูมิ for 2 days'\n" +
               "• 'plan 5 stations in นครราชสีมา for 1 day'\n\n" +
               "Or type 'change location' to select a different starting point.")

    def _execute_planning(self, request: str, location: Tuple[float, float], user_id: str = None) -> str:
        """Execute the actual planning request"""
        try:
            logger.info(f"Executing planning request: '{request}' from location {location}")
            result = self.planner.plan_inspection(request, location)

            # Check if this is a shortfall case (check for shortfall notice in response)
            if user_id and "Station Shortfall Notice" in result and "Would you like me to:" in result:
                # Store the shortfall context
                session = self.user_sessions[user_id]
                session['state'] = 'waiting_shortfall_response'
                session['last_shortfall_request'] = request
                session['last_shortfall_result'] = result

            return result
        except Exception as e:
            logger.error(f"Planning execution error: {e}")
            return f"❌ Error generating plan: {str(e)}\n\nPlease try rephrasing your request."

    def _handle_shortfall_response(self,
                                  user_id: str,
                                  message: str,
                                  user_location: Optional[Tuple[float, float]]) -> str:
        """Handle user response to station shortfall options"""
        session = self.user_sessions[user_id]
        message_lower = message.lower().strip()

        # Reset to ready state
        session['state'] = 'ready_for_planning'

        # Check user choice
        if any(keyword in message_lower for keyword in ['accept', 'yes', 'ok', 'approve', '✅']):
            return ("✅ **Plan Accepted!**\n\nGreat! The current plan provides a safe and manageable " +
                   "inspection schedule. You can start your inspection with confidence.\n\n" +
                   "You can request a new plan anytime!")

        elif any(keyword in message_lower for keyword in ['replan', 'extend', '3 days', 'three days', '🗓️']):
            # Generate new request for 3 days
            original_request = session.get('last_shortfall_request', '')
            modified_request = original_request.replace('2 day', '3 day').replace('2days', '3days')
            if '2' in original_request and 'day' in original_request:
                modified_request = original_request.replace('2', '3', 1)

            result = self._execute_planning(modified_request, session['location_choice']['coordinates'], user_id)
            return f"🔄 **Replanning for 3 days:**\n\n{result}"

        elif any(keyword in message_lower for keyword in ['earlier', 'early', '08:00', '8:00', '🌅']):
            return ("🌅 **Earlier Start Option:**\n\nTo start at 08:00 instead of 09:00, " +
                   "this would require system configuration changes. Currently, the system is " +
                   "set for 09:00-17:00 working hours.\n\nWould you like to accept the current " +
                   "plan instead, or extend to 3 days?")

        elif any(keyword in message_lower for keyword in ['later', 'extend time', '18:00', '6pm', '🌆']):
            return ("🌆 **Later End Option:**\n\nExtending to 18:00 is possible but not recommended " +
                   "for safety reasons (driving in the dark, fatigue). The 17:00 deadline ensures " +
                   "safe return.\n\nI recommend extending to 3 days instead. Would you like me to " +
                   "replan for 3 days?")

        elif any(keyword in message_lower for keyword in ['one province', 'focus', 'ชัยภูมิ only', 'นครราชสีมา only', '🎯']):
            return ("🎯 **Single Province Option:**\n\nPlease specify which province you'd like to focus on:\n" +
                   "- Type 'ชัยภูมิ only' for Chaiyaphum stations only\n" +
                   "- Type 'นครราชสีมา only' for Nakhon Ratchasima stations only\n\n" +
                   "This will allow more stations within the time constraints.")

        else:
            # Unclear response, show options again
            return ("💭 **Please Choose:**\n\n" +
                   "**Quick responses:**\n" +
                   "- Type 'accept' to keep the current safe plan\n" +
                   "- Type 'extend to 3 days' to get all 20 stations\n" +
                   "- Type 'focus on ชัยภูมิ' for one province only\n\n" +
                   "What would you prefer?")

    def _get_welcome_message(self) -> str:
        """Get welcome message"""
        return """🎯 **Welcome to FM Station Inspection Planner!**

I can help you plan FM station inspections with accurate travel times and multi-day scheduling.

**Example requests:**
• "find 10 stations in ชัยภูมิ for 2 days"
• "plan 5 stations in นครราชสีมา for 1 day"
• "give me a plan for 15 stations in บุรีรัมย์"

Just tell me what you need, and I'll ask for your starting location!

Type 'help' for more information."""

    def _get_help_message(self) -> str:
        """Get help message"""
        return """ℹ️ **FM Station Inspection Planner Help**

**How to use:**
1. Tell me your inspection needs (e.g., "find 10 stations in ชัยภูมิ for 2 days")
2. Choose your starting location:
   • Your current GPS location
   • NBTC23 base office in Chaiyaphum
3. Receive your optimized inspection plan!

**Supported provinces:**
• ชัยภูมิ (Chaiyaphum) - cyp
• นครราชสีมา (Nakhon Ratchasima) - nkr
• บุรีรัมย์ (Buriram) - brr

**Features:**
✅ Real-time travel times using road routing
✅ Multi-day planning with home return by 17:00
✅ Lunch break scheduling (12:00-13:00)
✅ Station optimization for minimum travel time

**Commands:**
• 'help' - Show this help
• 'change location' - Select new starting location
• 'reset' - Start over"""

    def reset_user_session(self, user_id: str) -> str:
        """Reset user session"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        return "🔄 Session reset! You can start a new planning request."

def main():
    """Simple console interface for testing"""
    print("🤖 FM Station Inspection Bot (Console Mode)")
    print("=" * 50)
    print("Type 'quit' to exit, 'help' for assistance")
    print()

    bot = FMStationBot()
    user_id = "console_user"

    try:
        while True:
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break

            if user_input.lower() == 'reset':
                response = bot.reset_user_session(user_id)
                print(f"\n🤖 Bot: {response}")
                continue

            # Simulate location sharing (for testing)
            user_location = None
            if user_input.lower() == 'share location':
                # Example GPS coordinates (Chaiyaphum city center)
                user_location = (15.8056, 102.0313)
                user_input = "shared location"

            response = bot.process_message(user_id, user_input, user_location)
            print(f"\n🤖 Bot: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()