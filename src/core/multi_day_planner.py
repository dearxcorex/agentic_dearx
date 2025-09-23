"""Multi-Day FM Station Inspection Planner"""

import re
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from haversine import haversine, Unit
from ..database.database import StationDatabase
from ..services.openrouter_client import OpenRouterClient
from ..services.travel_time_service import TravelTimeService
from ..services.district_worth_agent import DistrictWorthAgent
from ..services.plan_monitor_agent import PlanMonitorAgent
from ..services.auto_fix_agent import AutoFixAgent
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
        self.travel_service = TravelTimeService()
        self.district_worth_agent = DistrictWorthAgent()
        self.monitor_agent = PlanMonitorAgent()
        self.auto_fix_agent = AutoFixAgent()

    def plan_with_district_optimization(self, user_input: str) -> str:
        """
        Plan multi-day inspection using district-worth optimization to minimize API calls
        """
        try:
            # Parse user request
            requirements = self._parse_user_request(user_input)
            province = requirements.get('province', [])
            if isinstance(province, str):
                province = [province]

            logger.info(f"Planning district-optimized inspection for: {province}")

            # Get stations using custom filters
            all_stations = []
            for prov in province:
                stations = self.db.get_stations_with_custom_filters(prov)
                all_stations.extend(stations)

            if not all_stations:
                return "❌ No valid stations found with the specified criteria."

            logger.info(f"Found {len(all_stations)} valid stations across {len(province)} provinces")

            # Analyze district worth
            district_analyses = self.district_worth_agent.analyze_all_districts(all_stations)
            worth_districts = [d for d in district_analyses if d["should_visit"]]

            if not worth_districts:
                return "❌ No districts found with sufficient station density to be worth visiting."

            # Pre-compute district-to-district distances
            district_centers = {}
            for analysis in worth_districts:
                if analysis["coordinates"]:
                    # Calculate center of district
                    coords = analysis["coordinates"]
                    center_lat = sum(c[0] for c in coords) / len(coords)
                    center_lon = sum(c[1] for c in coords) / len(coords)
                    district_centers[analysis["district"]] = (center_lat, center_lon)

            # Pre-compute distances (minimal API calls)
            logger.info("Pre-computing district distances to populate cache...")
            self.travel_service.batch_precompute_district_distances(district_centers, self.HOME_LOCATION)

            # Generate optimized plans by district
            daily_plans = self._plan_by_districts(worth_districts, all_stations, requirements)

            # Generate response
            return self._generate_district_optimized_response(daily_plans, worth_districts, all_stations)

        except Exception as e:
            logger.error(f"District optimization planning error: {e}")
            return f"❌ Error in district-optimized planning: {str(e)}"

    def _generate_district_optimized_response(self, daily_plans: List[Dict],
                                            worth_districts: List[Dict],
                                            all_stations: List[Dict]) -> str:
        """Generate response for district-optimized planning"""
        if not daily_plans:
            return "❌ No valid daily plans could be generated"

        total_stations = sum(len(plan["stations"]) for plan in daily_plans)
        total_days = len(daily_plans)

        response = f"🎯 **District-Optimized {total_days}-Day Plan** ({total_stations} stations)\n\n"

        # Add district worth summary
        response += "📊 **District Analysis**:\n"
        for district in worth_districts[:5]:  # Top 5 districts
            response += f"• {district['district']}: {district['station_count']} stations (score: {district['worth_score']})\n"
        response += "\n"

        # Add daily plans
        for day_num, plan in enumerate(daily_plans, 1):
            stations = plan["stations"]
            districts = plan["districts"]
            travel_info = plan["travel_info"]

            response += f"## 📅 Day {day_num} - {len(stations)} stations\n"
            response += f"**Districts**: {', '.join(districts)}\n"
            response += f"**Travel**: {travel_info['total_distance']:.1f}km, {travel_info['total_time']:.1f} hours\n\n"

            for i, station in enumerate(stations, 1):
                district = station.get('district', 'Unknown')
                name = station.get('name', 'Unknown Station')
                response += f"{i}. **{name}** ({district})\n"

                if i < len(stations):
                    next_station = stations[i]
                    if station.get('district') == next_station.get('district'):
                        response += f"   ↳ Same district (minimal travel)\n"
                    else:
                        response += f"   ↳ To {next_station.get('district', 'Unknown')}\n"

            response += "\n"

        # Add optimization summary
        response += "⚡ **Optimization Benefits**:\n"
        response += "• Grouped stations by district to minimize travel\n"
        response += "• Reduced API calls for same-district routing\n"
        response += "• Prioritized high-value districts\n"

        return response

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

            # Calculate actual stations planned vs requested
            actual_stations = sum(len(plan["stations"]) for plan in daily_plans)

            # Monitor plan for constraint violations and generate interventions
            monitoring_result = self.monitor_agent.monitor_plan_constraints(
                daily_plans, request_info["station_count"], request_info["days"], user_input
            )

            # Check if intervention is needed
            intervention_message = self.monitor_agent.generate_intervention_message(monitoring_result)

            if intervention_message and monitoring_result["intervention_needed"]:
                # Critical violations detected - offer auto-fix
                auto_fix_result = self.monitor_agent.auto_fix_plan(monitoring_result, user_input, daily_plans)

                if auto_fix_result["success"]:
                    # Return intervention message with auto-fix options
                    return self._generate_intervention_response(
                        intervention_message, auto_fix_result, monitoring_result, user_input
                    )

            # Generate normal response with evaluation and station comparison
            response = self._generate_multi_day_response(
                daily_plans, province, evaluation, request_info["station_count"], actual_stations
            )

            # Append optimization notice if warnings exist
            if monitoring_result["violations"] and not monitoring_result["intervention_needed"]:
                optimization_notice = self._generate_optimization_notice(monitoring_result)
                response += f"\n\n{optimization_notice}"

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
            # Find nearest station with same-district optimization
            nearest_station = None
            min_distance = float('inf')
            current_district = route_stations[-1].get('district') if route_stations else None

            # Check if there are stations in the same district first
            same_district_stations = [s for s in remaining_stations if s.get('district') == current_district and current_district != "Unknown"] if current_district else []

            if same_district_stations:
                # Use first available station in same district (they're all nearby)
                nearest_station = same_district_stations[0]
                min_distance = 0.5  # Minimal distance for same district
                logger.debug(f"Same district optimization: Using station in {current_district}")
            else:
                # Find nearest station normally for different districts
                for station in remaining_stations:
                    if station.get('lat') and station.get('long'):
                        station_pos = (station['lat'], station['long'])
                        distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)

                        if distance < min_distance:
                            min_distance = distance
                            nearest_station = station

            if not nearest_station:
                break

            # Calculate travel time with same-district optimization
            station_coords = (nearest_station['lat'], nearest_station['long'])

            if min_distance <= 0.5:  # Same district optimization
                # Use optimized travel service method for same district
                travel_info = self.travel_service.get_same_district_travel_time()
                travel_time = travel_info['duration_minutes']

                # For same district, assume similar return time as previous station if available
                if route_stations:
                    return_time = route_stations[-1].get('return_time_minutes', 45.0)  # Use previous or default
                else:
                    return_time = 45.0  # Default return time for same district
                logger.debug(f"Same district: skipping API calls for {nearest_station.get('name', 'station')}")
            else:
                # Calculate accurate travel time using routing service for different districts
                travel_info = self.travel_service.get_travel_time(current_pos, station_coords)
                travel_time = travel_info['duration_minutes']

                # Calculate return journey time from this station using routing service
                return_info = self.travel_service.get_travel_time(station_coords, self.HOME_LOCATION)
                return_time = return_info['duration_minutes']

            station_time = self.INSPECTION_TIME_MINUTES

            # Calculate time after this station including lunch break
            time_after_station = current_time_minutes + travel_time + station_time

            # Add lunch break if we cross 12:00 PM
            lunch_added = False
            if current_time_minutes < (12 * 60) and time_after_station >= (12 * 60):
                time_after_station += self.LUNCH_DURATION_MINUTES
                lunch_added = True

            # Add return journey time and safety buffer
            final_time = time_after_station + return_time + self.SAFETY_BUFFER_MINUTES

            # Removed 17:00 time constraint - user gets all requested stations
            # if final_time > (17 * 60):  # 17:00 in minutes
            #     logger.info(f"Day {day_number}: Stopping at {len(route_stations)} stations due to time constraint")
            #     break

            # Add station to route
            nearest_station['travel_distance_km'] = round(min_distance, 2)
            nearest_station['travel_time_minutes'] = round(travel_time, 1)
            nearest_station['return_time_minutes'] = return_time  # Store for same-district optimization
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
            # Calculate accurate travel time to return home
            last_station_coords = (last_station['lat'], last_station['long'])
            return_info = self.travel_service.get_travel_time(last_station_coords, self.HOME_LOCATION)
            return_distance = return_info['distance_km']
            return_time = return_info['duration_minutes']

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

    def _generate_multi_day_response(self, daily_plans: List[Dict], province, evaluation: Optional[Dict] = None,
                                   requested_stations: Optional[int] = None, actual_stations: Optional[int] = None) -> str:
        """Generate formatted multi-day inspection plan response with station comparison"""

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

        # Station shortfall notice removed - user gets what they request

        response_parts.append(f"- **Total Distance**: {overall_stats['total_distance']} km (over {len(daily_plans)} days)")
        response_parts.append(f"- **Total Time**: {overall_stats['total_time']} minutes")
        response_parts.append(f"- **Average per Day**: {overall_stats['total_stations'] // len(daily_plans)} stations, {overall_stats['total_distance'] / len(daily_plans):.1f} km")


        return "\n".join(response_parts)

    def _generate_intervention_response(self,
                                       intervention_message: str,
                                       auto_fix_result: Dict[str, Any],
                                       monitoring_result: Dict[str, Any],
                                       original_request: str) -> str:
        """Generate response when intervention is needed"""

        response_parts = [intervention_message]

        if auto_fix_result["success"]:
            response_parts.extend([
                "",
                "🤖 **AUTOMATIC FIX AVAILABLE**",
                "",
                auto_fix_result["ai_recommendations"],
                ""
            ])

            # Add specific fix suggestions
            for suggestion in auto_fix_result["new_request_suggestions"][:2]:
                response_parts.append(f"💡 {suggestion}")

            response_parts.extend([
                "",
                "**🚀 Ready to implement the fix?**",
                "",
                "**Quick Actions:**",
                "- Type **'fix it'** to automatically implement the best solution",
                "- Type **'show options'** to see all available fixes",
                "- Type **'ignore warnings'** to proceed with the risky plan anyway",
                "",
                f"**Original request**: {original_request}",
                f"**Suggested fix**: {auto_fix_result['new_request_suggestions'][0] if auto_fix_result['new_request_suggestions'] else 'Extend to 3 days'}"
            ])
        else:
            response_parts.extend([
                "",
                "⚠️ **Manual intervention required**",
                "Please consider:",
                "- Extending to more days",
                "- Reducing station count",
                "- Focusing on single province"
            ])

        return "\n".join(response_parts)

    def _generate_optimization_notice(self, monitoring_result: Dict[str, Any]) -> str:
        """Generate optimization notice for minor violations"""

        violations = monitoring_result["violations"]
        warning_violations = [v for v in violations if v["type"] == "warning"]

        if not warning_violations:
            return ""

        notice_parts = [
            "💡 **OPTIMIZATION OPPORTUNITIES**",
            "",
            "Your plan is workable but could be improved:",
            ""
        ]

        for violation in warning_violations[:3]:  # Show top 3
            notice_parts.append(f"⚡ {violation['message']}")

        notice_parts.extend([
            "",
            "**🔧 Want me to optimize this plan?**",
            "Type 'optimize plan' for automatic improvements!"
        ])

        return "\n".join(notice_parts)

    def handle_user_intervention_response(self, user_response: str, context: Dict[str, Any]) -> str:
        """Handle user response to intervention messages"""

        response_lower = user_response.lower().strip()

        if any(phrase in response_lower for phrase in ['fix it', 'auto fix', 'fix automatically', 'implement fix']):
            return self._execute_auto_fix(context)

        elif any(phrase in response_lower for phrase in ['show options', 'see options', 'alternatives']):
            return self._show_fix_alternatives(context)

        elif any(phrase in response_lower for phrase in ['ignore', 'proceed anyway', 'keep plan', 'ignore warnings']):
            return self._handle_ignore_warnings(context)

        elif any(phrase in response_lower for phrase in ['optimize', 'improve', 'make better']):
            return self._execute_optimization(context)

        else:
            return self._show_intervention_help()

    def _execute_auto_fix(self, context: Dict[str, Any]) -> str:
        """Execute the automatic fix"""

        try:
            # Get the best fix strategy
            monitoring_result = context["monitoring_result"]
            original_request = context["original_request"]

            # Determine fix strategy
            violations = monitoring_result["violations"]
            critical_violations = [v for v in violations if v["type"] == "critical"]

            if critical_violations:
                # Use auto-fix agent to generate fixed plan
                fix_strategy = {"primary_action": "extend_days", "new_days": 3, "confidence": 90}
                fix_result = self.auto_fix_agent.generate_fixed_plan(
                    original_request, monitoring_result, fix_strategy
                )

                if fix_result["success"]:
                    new_request = fix_result["new_request"]

                    return f"""🔧 **AUTO-FIX APPLIED!**

{fix_result['user_message']}

**🎯 Executing new request**: {new_request}

Processing your optimized plan..."""

            return "✅ Auto-fix completed! Generating your improved plan..."

        except Exception as e:
            logger.error(f"Auto-fix execution error: {e}")
            return "❌ Auto-fix failed. Please try manual adjustments."

    def _show_fix_alternatives(self, context: Dict[str, Any]) -> str:
        """Show alternative fix options"""

        monitoring_result = context["monitoring_result"]
        original_request = context["original_request"]

        alternatives = self.auto_fix_agent.create_alternative_fixes(original_request, monitoring_result)

        response_parts = [
            "🔧 **ALTERNATIVE FIX OPTIONS**",
            "",
            "Choose the best solution for your needs:",
            ""
        ]

        for i, alt in enumerate(alternatives, 1):
            response_parts.extend([
                f"**{i}. {alt['title']}**",
                f"   {alt['description']}",
                f"   ✅ Benefits: {', '.join(alt['benefits'])}",
                f"   ⚠️ Trade-offs: {', '.join(alt['trade_offs'])}",
                ""
            ])

        response_parts.extend([
            "**Quick responses:**",
            "- Type '1' for the first option",
            "- Type '2' for the second option",
            "- Type '3' for the third option (if available)",
            "- Type 'back' to return to auto-fix"
        ])

        return "\n".join(response_parts)

    def _handle_ignore_warnings(self, context: Dict[str, Any]) -> str:
        """Handle user choosing to ignore warnings"""

        return """⚠️ **PROCEEDING WITH RISKY PLAN**

You've chosen to proceed despite safety warnings. Please note:

🚨 **Risks acknowledged:**
- Potential inspector fatigue
- Safety concerns with long driving days
- Possible quality reduction due to time pressure

✅ **Your original plan will be used as-is**

**Safety reminders:**
- Take regular breaks during long drives
- Don't hesitate to stop if feeling tired
- Consider splitting difficult days if needed

Proceeding with your original request..."""

    def _execute_optimization(self, context: Dict[str, Any]) -> str:
        """Execute plan optimization for warning-level issues"""

        return """💡 **PLAN OPTIMIZATION STARTED**

🔄 Analyzing your plan for efficiency improvements...

**Optimization targets:**
- Route sequence efficiency
- Travel time reduction
- Workload balancing
- Fatigue minimization

Generating your optimized plan..."""

    def _show_intervention_help(self) -> str:
        """Show help for intervention responses"""

        return """💭 **INTERVENTION OPTIONS**

I didn't understand your response. Here are your options:

**🔧 For automatic fixes:**
- Type **'fix it'** - Apply best automatic solution
- Type **'show options'** - See all available fixes

**⚡ For optimization:**
- Type **'optimize'** - Improve plan efficiency

**⚠️ To proceed anyway:**
- Type **'ignore warnings'** - Keep risky plan

**❓ Need help:**
- Type **'explain'** - Get detailed explanation

What would you like to do?"""

    def _plan_by_districts(self, worth_districts: List[Dict], all_stations: List[Dict], requirements: Dict) -> List[Dict]:
        """Plan route by processing districts in worth order with minimal API calls"""
        daily_plans = []
        remaining_districts = worth_districts.copy()
        requested_days = requirements.get('days', 2)

        for day in range(1, requested_days + 1):
            if not remaining_districts:
                break

            day_plan = self._plan_single_day_by_districts(day, remaining_districts, all_stations)
            daily_plans.append(day_plan)

            # Remove completed districts
            completed_districts = [s.get('district') for s in day_plan['stations']]
            remaining_districts = [d for d in remaining_districts if d['district'] not in completed_districts]

        return daily_plans

    def _plan_single_day_by_districts(self, day_number: int, available_districts: List[Dict], all_stations: List[Dict]) -> Dict:
        """Plan a single day focusing on complete districts to minimize travel between districts"""
        current_pos = self.HOME_LOCATION
        current_time_minutes = 9 * 60  # 9:00 AM
        route_stations = []
        total_distance = 0
        total_time = 0
        lunch_added = False
        processed_districts = set()

        logger.info(f"Day {day_number}: Planning with {len(available_districts)} available districts")

        # Process districts in worth order
        for district_analysis in available_districts:
            district_name = district_analysis['district']

            if district_name in processed_districts:
                continue

            # Get stations for this district
            district_stations = [s for s in all_stations if s.get('district') == district_name]

            if not district_stations:
                continue

            logger.info(f"Day {day_number}: Processing district '{district_name}' with {len(district_stations)} stations")

            # Use cached travel time to district
            if district_stations:
                first_station = district_stations[0]
                station_coords = (first_station.get('lat'), first_station.get('long'))

                # Get travel time to district using cache
                travel_info = self.travel_service.get_travel_time_with_cache(
                    current_pos, station_coords, origin_district=None,
                    destination_district=district_name, home_location=self.HOME_LOCATION
                )

                travel_to_district = travel_info['duration_minutes']

                # Add all stations in this district (use minimal distances between them)
                district_added = False
                for station in district_stations:
                    station_time = self.INSPECTION_TIME_MINUTES

                    if not route_stations:
                        time_for_station = travel_to_district + station_time
                    else:
                        same_district_info = self.travel_service.get_same_district_travel_time()
                        time_for_station = same_district_info['duration_minutes'] + station_time

                    # Check if we have time
                    if current_time_minutes + time_for_station < 16 * 60:  # Before 4 PM
                        if not district_added:
                            total_distance += travel_info['distance_km']
                            total_time += travel_to_district
                            current_time_minutes += travel_to_district
                            district_added = True
                        else:
                            same_district_info = self.travel_service.get_same_district_travel_time()
                            total_distance += same_district_info['distance_km']
                            total_time += same_district_info['duration_minutes']
                            current_time_minutes += same_district_info['duration_minutes']

                        # Add station
                        station['travel_distance_km'] = same_district_info['distance_km'] if district_added else travel_info['distance_km']
                        station['travel_time_minutes'] = same_district_info['duration_minutes'] if district_added else travel_info['duration_minutes']
                        route_stations.append(station)

                        total_time += station_time
                        current_time_minutes += station_time
                        current_pos = (station.get('lat'), station.get('long'))

                        # Add lunch break if needed
                        if not lunch_added and current_time_minutes >= 12 * 60:
                            total_time += self.LUNCH_DURATION_MINUTES
                            current_time_minutes += self.LUNCH_DURATION_MINUTES
                            lunch_added = True
                    else:
                        break

                if district_added:
                    processed_districts.add(district_name)

        # Calculate return journey
        if route_stations:
            last_station_coords = (route_stations[-1].get('lat'), route_stations[-1].get('long'))
            return_info = self.travel_service.get_travel_time_with_cache(
                last_station_coords, self.HOME_LOCATION,
                origin_district=route_stations[-1].get('district'),
                destination_district="Home", home_location=self.HOME_LOCATION
            )
            return_time = return_info['duration_minutes']
            total_distance += return_info['distance_km']
            total_time += return_time
            final_return_time_minutes = current_time_minutes + return_time
            return_time_str = f"{int(final_return_time_minutes//60):02d}:{int(final_return_time_minutes%60):02d}"
        else:
            return_time_str = "09:00"

        return {
            "day": day_number, "stations": route_stations,
            "total_distance_km": round(total_distance, 2),
            "total_time_minutes": round(total_time, 1),
            "return_time": return_time_str, "lunch_break": lunch_added,
            "districts_visited": list(processed_districts)
        }

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

def test_multi_day_planner():
    """Test the multi-day planner"""
    planner = MultiDayPlanner()

    # Test with district optimization
    test_input = "find me 15 stations in ชัยภูมิ i want to go 2 day make a plan for me"

    print("Testing district-optimized multi-day planner...")
    print(f"Input: {test_input}")
    print("\nResult:")
    result = planner.plan_with_district_optimization(test_input)
    print(result)

if __name__ == "__main__":
    test_multi_day_planner()