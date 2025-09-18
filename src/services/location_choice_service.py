"""
Location Choice Service for FM Station Inspection Bot
Handles user location vs NBTC23 base location selection
"""

from typing import Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class LocationChoiceService:
    """Service for handling location choice in the bot interface"""

    # NBTC Region 23 Office Location (ชัยภูมิ)
    NBTC23_LOCATION = (14.78524443450366, 102.04253370526135)
    NBTC23_NAME = "NBTC Region 23 Office (ชัยภูมิ)"

    def __init__(self):
        self.user_choice_cache = {}  # Cache user's last choice

    def get_location_choice_prompt(self, user_id: Optional[str] = None) -> str:
        """
        Generate location choice prompt for the user

        Args:
            user_id: Optional user identifier for caching preferences

        Returns:
            Formatted prompt asking user to choose location
        """
        prompt = """📍 **Choose Your Starting Location**

Please select your starting location for the inspection plan:

1️⃣ **Use Your Current Location** 📱
   - Share your GPS location for personalized routing
   - More accurate travel times from your position

2️⃣ **Use NBTC23 Base Location** 🏢
   - NBTC Region 23 Office in Chaiyaphum
   - Standard starting point for official inspections
   - Location: 14.785244, 102.042534

**Reply with:**
• `1` or `current` for your location
• `2` or `base` for NBTC23 base

Or simply share your location if you want to use option 1."""

        # Add last choice if user has one cached
        if user_id and user_id in self.user_choice_cache:
            last_choice = self.user_choice_cache[user_id]
            prompt += f"\n\n💡 *Last used: {last_choice['name']}*"

        return prompt

    def parse_location_choice(self,
                            user_input: str,
                            user_location: Optional[Tuple[float, float]] = None,
                            user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse user's location choice from input

        Args:
            user_input: User's response to location choice
            user_location: User's GPS coordinates if shared
            user_id: Optional user identifier for caching

        Returns:
            Dictionary with location choice information
        """
        user_input_lower = user_input.lower().strip()

        # Check if user shared GPS location
        if user_location is not None:
            choice = {
                'type': 'user_location',
                'coordinates': user_location,
                'name': f"Your Location ({user_location[0]:.6f}, {user_location[1]:.6f})",
                'description': "Using your current GPS location"
            }
            if user_id:
                self.user_choice_cache[user_id] = choice
            return choice

        # Parse text choices
        if user_input_lower in ['1', 'current', 'my location', 'current location', 'gps']:
            return {
                'type': 'request_location',
                'coordinates': None,
                'name': "Waiting for GPS location",
                'description': "Please share your current location"
            }

        elif user_input_lower in ['2', 'base', 'nbtc', 'nbtc23', 'office', 'base location']:
            choice = {
                'type': 'nbtc23_base',
                'coordinates': self.NBTC23_LOCATION,
                'name': self.NBTC23_NAME,
                'description': "Using NBTC Region 23 Office as starting point"
            }
            if user_id:
                self.user_choice_cache[user_id] = choice
            return choice

        # Default: unclear choice
        return {
            'type': 'unclear',
            'coordinates': None,
            'name': "Choice unclear",
            'description': "Please specify 1 (current location) or 2 (NBTC23 base)"
        }

    def get_location_confirmation(self, choice: Dict[str, Any]) -> str:
        """
        Generate confirmation message for location choice

        Args:
            choice: Location choice dictionary

        Returns:
            Formatted confirmation message
        """
        if choice['type'] == 'user_location':
            return f"✅ **Location Confirmed**\n📍 Using your current location: {choice['coordinates'][0]:.6f}, {choice['coordinates'][1]:.6f}\n\nNow you can request your inspection plan!"

        elif choice['type'] == 'nbtc23_base':
            return f"✅ **Location Confirmed**\n🏢 Using {choice['name']}\n📍 Coordinates: {choice['coordinates'][0]:.6f}, {choice['coordinates'][1]:.6f}\n\nNow you can request your inspection plan!"

        elif choice['type'] == 'request_location':
            return "📱 **Please Share Your Location**\n\nTap the location button (📍) or share your GPS coordinates to use your current location for the inspection plan."

        else:  # unclear
            return "❓ **Please Choose Location**\n\n" + self.get_location_choice_prompt()

    def should_ask_location_choice(self, user_input: str) -> bool:
        """
        Determine if we should ask for location choice based on user input

        Args:
            user_input: User's message

        Returns:
            True if location choice should be requested
        """
        # Keywords that indicate user wants to plan inspections
        planning_keywords = [
            'plan', 'find', 'stations', 'inspection', 'visit', 'trip',
            'แผน', 'หา', 'สถานี', 'ตรวจ', 'เที่ยว', 'ไป'
        ]

        # Check if user input contains planning keywords
        user_input_lower = user_input.lower()
        has_planning_keyword = any(keyword in user_input_lower for keyword in planning_keywords)

        # Also check for numbers (like "10 stations")
        has_numbers = any(char.isdigit() for char in user_input)

        return has_planning_keyword and has_numbers

    def get_user_preference(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's cached location preference

        Args:
            user_id: User identifier

        Returns:
            Cached location choice or None
        """
        return self.user_choice_cache.get(user_id)

    def clear_user_preference(self, user_id: str) -> bool:
        """
        Clear user's cached location preference

        Args:
            user_id: User identifier

        Returns:
            True if preference was cleared
        """
        if user_id in self.user_choice_cache:
            del self.user_choice_cache[user_id]
            return True
        return False

    def format_location_info(self, location: Tuple[float, float], name: str = None) -> str:
        """
        Format location information for display

        Args:
            location: (lat, lon) coordinates
            name: Optional location name

        Returns:
            Formatted location string
        """
        if name:
            return f"📍 **{name}**\nCoordinates: {location[0]:.6f}, {location[1]:.6f}"
        else:
            return f"📍 Location: {location[0]:.6f}, {location[1]:.6f}"