"""Multi-Day FM Station Inspection Planner"""

import re
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from haversine import haversine, Unit
from ..database.database import StationDatabase
from ..services.openrouter_client import OpenRouterClient
from ..config.config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiDayPlanner:
    """Multi-day FM station inspection planner with home return requirements"""

    # Inspector's home location
    HOME_LOCATION = (14.78524443450366, 102.04253370526135)

    # Operating constraints
    DAILY_START_TIME = "09:00"  # 9:00 AM
    DAILY_END_TIME = "17:00"    # 5:00 PM (must be home by this time)
    LUNCH_START_TIME = "12:00"  # 12:00 PM lunch break start
    LUNCH_END_TIME = "13:00"    # 1:00 PM lunch break end
    LUNCH_DURATION_MINUTES = 60  # 1 hour lunch break
    INSPECTION_TIME_MINUTES = 10  # Minutes per station
    AVERAGE_SPEED_KMH = 100      # Average travel speed with car using Google Maps
    SAFETY_BUFFER_MINUTES = 30   # Safety buffer for return journey

    def __init__(self):
        self.db = StationDatabase()
        self.llm_client = OpenRouterClient()

    def plan_multi_day_inspection(self, user_input: str) -> str:
        """
        Plan multi-day FM station inspection with automatic home return

        Args:
            user_input: User request (e.g., "find me 10 stations in ชัยภูมิ i want to go 2 day")

        Returns:
            Detailed multi-day inspection plan
        """
        try:
            # Parse user input
            request_info = self._parse_multi_day_request(user_input)

            if not request_info:
                return "Sorry, I couldn't understand your multi-day inspection request. Please specify province, number of stations, and number of days."

            province = request_info["province"]
            station_count = request_info["station_count"]
            days = request_info["days"]

            logger.info(f"Planning {days}-day inspection: {station_count} stations in {province}")

            # Handle multiple provinces
            available_stations = []
            if isinstance(province, list):
                # Multi-province request
                for prov in province:
                    stations = self.db.get_stations_by_province(prov, limit=1000)
                    if stations:
                        available_stations.extend(stations)
                        logger.info(f"Found {len(stations)} stations in {prov}")
                    else:
                        logger.warning(f"No stations found in {prov}")

                if not available_stations:
                    return f"No available stations found in any of the requested provinces: {', '.join(province)}"

            else:
                # Single province request
                available_stations = self.db.get_stations_by_province(province, limit=1000)
                if not available_stations:
                    return f"No available stations found in {province}. Please check if the province name is correct."

            # Add distances from home
            available_stations = self.db.enrich_stations_with_distance(
                available_stations, self.HOME_LOCATION
            )

            # Limit to requested count
            if len(available_stations) < station_count:
                station_count = len(available_stations)
                logger.info(f"Adjusted station count to {station_count} (all available stations)")

            selected_stations = available_stations[:station_count]

            # Plan days
            daily_plans = self._plan_daily_routes(selected_stations, days)

            # Evaluate plan with fatigue and day extension analysis
            evaluation = self._evaluate_multi_day_plan(daily_plans, days, selected_stations)

            # Generate response with evaluation
            response = self._generate_multi_day_response(daily_plans, province, evaluation)

            return response

        except Exception as e:
            logger.error(f"Multi-day planning error: {e}")
            return f"Sorry, an error occurred during multi-day planning: {str(e)}"

    def _parse_multi_day_request(self, user_input: str) -> Optional[Dict]:
        """Parse user input for multi-day planning parameters"""
        try:
            # Convert to lowercase for easier matching
            input_lower = user_input.lower()

            # Extract numbers
            numbers = re.findall(r'\d+', user_input)

            # Province mapping - Thai names, English names, and abbreviations
            province_mappings = {
                # Thai names
                "ชัยภูมิ": "ชัยภูมิ",
                "นครราชสีมา": "นครราชสีมา",
                "บุรีรัมย์": "บุรีรัมย์",
                # English names
                "chaiyaphum": "ชัยภูมิ",
                "nakhon ratchasima": "นครราชสีมา",
                "nakorn ratchasima": "นครราชสีมา",
                "nakhonratchasima": "นครราชสีมา",
                "nakornratchasima": "นครราชสีมา",
                "buriram": "บุรีรัมย์",
                "buri ram": "บุรีรัมย์",
                # Abbreviations
                "cyp": "ชัยภูมิ",
                "nkr": "นครราชสีมา",
                "brr": "บุรีรัมย์"
            }

            # Find matching provinces
            matched_provinces = []
            for key, thai_name in province_mappings.items():
                if key in input_lower:
                    if thai_name not in matched_provinces:
                        matched_provinces.append(thai_name)

            # Handle multi-province requests
            if len(matched_provinces) > 1:
                logger.info(f"Multi-province request detected: {matched_provinces}")
                # Use all matched provinces for multi-province planning
                province = matched_provinces  # Pass all provinces
                logger.info(f"Planning for multiple provinces: {province}")
            elif len(matched_provinces) == 1:
                province = matched_provinces[0]
            else:
                logger.warning(f"No valid province found in: {user_input}")
                return None

            # Determine station count and days
            station_count = 10  # default
            days = 1  # default

            if len(numbers) >= 1:
                station_count = int(numbers[0])
            if len(numbers) >= 2:
                days = int(numbers[1])
            elif "2 day" in input_lower or "two day" in input_lower or "2day" in input_lower:
                days = 2

            logger.info(f"Parsed request: {station_count} stations in {province} for {days} days")

            return {
                "province": province,
                "station_count": station_count,
                "days": days,
                "all_provinces": matched_provinces  # For future multi-province support
            }

        except Exception as e:
            logger.error(f"Request parsing error: {e}")
            return None

    def _plan_daily_routes(self, stations: List[Dict], days: int) -> List[Dict]:
        """Plan optimal daily routes with home return constraint"""

        # Distribute stations across days
        stations_per_day = len(stations) // days
        remainder = len(stations) % days

        daily_plans = []
        station_index = 0

        for day in range(days):
            # Calculate stations for this day
            day_station_count = stations_per_day
            if day < remainder:
                day_station_count += 1

            # Get stations for this day
            day_stations = stations[station_index:station_index + day_station_count]
            station_index += day_station_count

            # Plan route for this day
            day_plan = self._plan_single_day_route(day_stations, day + 1)
            daily_plans.append(day_plan)

        return daily_plans

    def _plan_single_day_route(self, stations: List[Dict], day_number: int) -> Dict:
        """Plan optimal route for a single day with time constraints"""

        if not stations:
            return {
                "day": day_number,
                "stations": [],
                "total_distance_km": 0,
                "total_time_minutes": 0,
                "return_time": self.DAILY_START_TIME,
                "feasible": True
            }

        # Start from home
        current_pos = self.HOME_LOCATION
        route_stations = []
        total_distance = 0
        total_time = 0

        # Track available stations
        remaining_stations = stations.copy()

        # Start time (9:00 AM)
        current_time_minutes = 9 * 60  # 9:00 AM in minutes

        while remaining_stations:
            # Find nearest station
            nearest_station = None
            min_distance = float('inf')

            for station in remaining_stations:
                if station.get('lat') and station.get('long'):
                    station_pos = (station['lat'], station['long'])
                    distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_station = station

            if not nearest_station:
                break

            # Calculate time for this station
            travel_time = (min_distance / self.AVERAGE_SPEED_KMH) * 60  # minutes
            station_time = self.INSPECTION_TIME_MINUTES

            # Calculate return journey time from this station
            return_distance = haversine(
                (nearest_station['lat'], nearest_station['long']),
                self.HOME_LOCATION,
                unit=Unit.KILOMETERS
            )
            return_time = (return_distance / self.AVERAGE_SPEED_KMH) * 60

            # Calculate time after this station including lunch break
            time_after_station = current_time_minutes + travel_time + station_time

            # Add lunch break if we cross 12:00 PM
            lunch_added = False
            if current_time_minutes < (12 * 60) and time_after_station >= (12 * 60):
                time_after_station += self.LUNCH_DURATION_MINUTES
                lunch_added = True

            # Add return journey time and safety buffer
            final_time = time_after_station + return_time + self.SAFETY_BUFFER_MINUTES

            if final_time > (17 * 60):  # 17:00 in minutes
                logger.info(f"Day {day_number}: Stopping at {len(route_stations)} stations due to time constraint (would finish at {final_time//60:02d}:{final_time%60:02d})")
                break

            # Add station to route
            nearest_station['travel_distance_km'] = round(min_distance, 2)
            nearest_station['travel_time_minutes'] = round(travel_time, 1)
            route_stations.append(nearest_station)

            # Update totals
            total_distance += min_distance
            total_time += travel_time + station_time
            current_time_minutes += travel_time + station_time

            # Add lunch break time if we crossed 12:00 PM
            if lunch_added:
                total_time += self.LUNCH_DURATION_MINUTES
                current_time_minutes += self.LUNCH_DURATION_MINUTES
                logger.info(f"Day {day_number}: Added lunch break after station {len(route_stations)}")

            # Update position and remove station
            current_pos = (nearest_station['lat'], nearest_station['long'])
            remaining_stations.remove(nearest_station)

        # Calculate return journey
        if route_stations:
            last_station = route_stations[-1]
            return_distance = haversine(
                (last_station['lat'], last_station['long']),
                self.HOME_LOCATION,
                unit=Unit.KILOMETERS
            )
            return_time = (return_distance / self.AVERAGE_SPEED_KMH) * 60

            total_distance += return_distance
            total_time += return_time

            # Calculate return arrival time
            final_time_minutes = current_time_minutes + return_time
            return_hours = int(final_time_minutes // 60)
            return_mins = int(final_time_minutes % 60)
            return_time_str = f"{return_hours:02d}:{return_mins:02d}"
        else:
            return_time_str = self.DAILY_START_TIME

        return {
            "day": day_number,
            "stations": route_stations,
            "total_distance_km": round(total_distance, 2),
            "total_time_minutes": round(total_time, 1),
            "return_time": return_time_str,
            "feasible": len(route_stations) > 0 or len(stations) == 0
        }

    def _evaluate_multi_day_plan(self, daily_plans: List[Dict], requested_days: int, all_stations: List[Dict]) -> Dict[str, Any]:
        """Evaluate the multi-day plan for fatigue and safety"""
        try:
            from ..services.plan_evaluator import PlanEvaluationAgent

            evaluator = PlanEvaluationAgent()

            # Use all stations for route evaluation
            evaluation = evaluator.evaluate_plan(
                stations=all_stations,
                start_location=self.HOME_LOCATION,
                route_info={},
                daily_plans=daily_plans,
                requested_days=requested_days
            )

            logger.info(f"Multi-day plan evaluation: Score {evaluation.get('score', 0)}/100")

            # Log day extension recommendations
            day_rec = evaluation.get('day_recommendation', {})
            if day_rec.get('extend_days', False):
                logger.warning(f"Day extension recommended: {day_rec.get('message', 'N/A')}")

            # Log fatigue analysis
            fatigue = evaluation.get('fatigue_analysis', {})
            if fatigue.get('is_too_demanding', False):
                logger.warning(f"Plan is too demanding: {fatigue.get('fatigue_level', 'unknown')} fatigue level")

            return evaluation

        except Exception as e:
            logger.error(f"Plan evaluation failed: {e}")
            return {"is_optimal": True, "score": 75, "error": str(e)}

    def _generate_multi_day_response(self, daily_plans: List[Dict], province, evaluation: Optional[Dict] = None) -> str:
        """Generate formatted multi-day inspection plan response"""

        response_parts = []

        # Handle multiple provinces in title
        if isinstance(province, list):
            province_str = " & ".join(province)
            response_parts.append(f"# Multi-Day FM Station Inspection Plan - {province_str}")
        else:
            response_parts.append(f"# Multi-Day FM Station Inspection Plan - {province}")

        response_parts.append(f"**Home Base**: {self.HOME_LOCATION[0]:.6f}, {self.HOME_LOCATION[1]:.6f}")
        response_parts.append("")

        overall_stats = {
            "total_stations": 0,
            "total_distance": 0,
            "total_time": 0
        }

        for day_plan in daily_plans:
            day_num = day_plan["day"]
            stations = day_plan["stations"]

            response_parts.append(f"## Day {day_num} Plan ({len(stations)} stations)")
            response_parts.append("")

            if not stations:
                response_parts.append("No stations planned for this day.")
                response_parts.append("")
                continue

            # List stations
            for i, station in enumerate(stations, 1):
                response_parts.append(f"{i}. **Station Name**: {station.get('name', 'Unknown')}")
                response_parts.append(f"   - **Frequency**: {station.get('freq', 'Unknown')} MHz")
                response_parts.append(f"   - **Province**: {station.get('province', 'Unknown')}")
                response_parts.append(f"   - **District**: {station.get('district', 'Unknown')}")
                response_parts.append(f"   - **Distance**: {station.get('travel_distance_km', 0)} km from previous location")
                response_parts.append(f"   - **Travel Time**: {station.get('travel_time_minutes', 0)} minutes")
                response_parts.append("")

            # Day summary
            response_parts.append(f"**Day {day_num} Summary:**")
            response_parts.append(f"- **Start Time**: {self.DAILY_START_TIME}")
            response_parts.append(f"- **Lunch Break**: {self.LUNCH_START_TIME} - {self.LUNCH_END_TIME} (1 hour)")
            response_parts.append(f"- **Total Distance**: {day_plan['total_distance_km']} km")
            response_parts.append(f"- **Travel Time**: {day_plan['total_time_minutes']} minutes")
            response_parts.append(f"- **Inspection Time**: {len(stations) * self.INSPECTION_TIME_MINUTES} minutes")
            response_parts.append(f"- **Return Home Time**: {day_plan['return_time']} (estimated arrival time)")
            response_parts.append(f"- **Estimated Return**: Will arrive home at {day_plan['return_time']}")

            if day_plan['return_time'] > "17:00":
                response_parts.append(f"- **⚠️ Warning**: Return time exceeds 17:00 limit")
            else:
                response_parts.append(f"- **✅ Status**: Within time constraints")

            response_parts.append("")

            # Update overall stats
            overall_stats["total_stations"] += len(stations)
            overall_stats["total_distance"] += day_plan["total_distance_km"]
            overall_stats["total_time"] += day_plan["total_time_minutes"]

        # Overall summary
        response_parts.append("## Overall Summary")
        response_parts.append(f"- **Total Stations**: {overall_stats['total_stations']}")
        response_parts.append(f"- **Total Distance**: {overall_stats['total_distance']} km (over {len(daily_plans)} days)")
        response_parts.append(f"- **Total Time**: {overall_stats['total_time']} minutes")
        response_parts.append(f"- **Average per Day**: {overall_stats['total_stations'] // len(daily_plans)} stations, {overall_stats['total_distance'] / len(daily_plans):.1f} km")


        return "\n".join(response_parts)

def test_multi_day_planner():
    """Test the multi-day planner"""
    planner = MultiDayPlanner()

    # Test request
    test_input = "find me 10 stations in ชัยภูมิ i want to go 2 day make a plan for me"

    print("Testing multi-day planner...")
    print(f"Input: {test_input}")
    print("\nResult:")
    result = planner.plan_multi_day_inspection(test_input)
    print(result)

if __name__ == "__main__":
    test_multi_day_planner()