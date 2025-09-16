"""LangGraph nodes for FM Station Planning"""

from typing import Dict, List, Optional, Tuple, Any, Annotated, Union
from typing_extensions import TypedDict
import json
import re
from geopy.geocoders import Nominatim
from openrouter_client import OpenRouterClient
from database import StationDatabase
from location_tool import LocationTool
from config import Config
import logging
import operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FMStationState(TypedDict):
    """State for the FM Station Planning workflow"""
    user_input: str  # Original user input
    requirements: Dict[str, Any]  # Extracted requirements
    location_coords: Dict[str, Any]  # Location coordinates
    start_location: Dict[str, Any]  # Starting point for route
    stations: List[Dict[str, Any]]  # Found stations
    route_info: Dict[str, Any]  # Route optimization results
    stations_ordered: List[Dict[str, Any]]  # Stations in optimal order
    current_location: Union[Tuple[float, float], None]  # Real-time GPS coordinates
    location_based_plan: Dict[str, Any]  # Location-based inspection plan
    plan_evaluation: Dict[str, Any]  # Plan evaluation results
    final_response: str  # Final response
    errors: Annotated[List[str], operator.add]  # Accumulated errors

    # New fields for step-by-step workflow
    step_by_step_mode: bool  # Whether using step-by-step approach
    visited_station_ids: List[str]  # IDs of stations already planned/visited
    current_step: int  # Current step in the process
    nearest_station: Optional[Dict[str, Any]]  # Current nearest station

def language_processing_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for parsing Thai user input and extracting requirements"""
    try:
        llm_client = OpenRouterClient()
        user_input = state["user_input"]

        # Extract numbers from text
        numbers = re.findall(r'\d+', user_input)
        station_count = int(numbers[0]) if numbers else 10
        time_minutes = None

        # Look for time constraints
        if len(numbers) >= 2:
            # Check for time range (e.g., "30-40 minutes")
            if "-" in user_input:
                time_parts = re.findall(r'(\d+)-(\d+)', user_input)
                if time_parts:
                    time_minutes = int(time_parts[0][1])  # Use upper bound
            else:
                time_minutes = int(numbers[1])

        # Use LLM to parse location
        location_info = llm_client.parse_location(user_input)

        requirements = {
            "original_text": user_input,
            "location": location_info,
            "station_count": station_count,
            "time_constraint_minutes": time_minutes,
            "needs_route": "route" in user_input.lower() or "plan" in user_input.lower()
        }

        logger.info(f"Extracted requirements: {requirements}")

        return {"requirements": requirements}

    except Exception as e:
        logger.error(f"Language processing error: {e}")
        return {"errors": [f"Language processing failed: {str(e)}"]}

# Thai province coordinates (fallback data)
THAI_PROVINCES = {
    "ชัยภูมิ": (15.8068, 102.0348),
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "เชียงใหม่": (18.7883, 98.9853),
    "ภูเก็ต": (7.8804, 98.3923),
    "ขอนแก่น": (16.4322, 102.8236),
    "นครราชสีมา": (14.9799, 102.0977),
    "อุดรธานี": (17.4138, 102.7877),
    "สงขลา": (7.1894, 100.5954),
    "ระยอง": (12.6814, 101.2816),
    "ชลบุรี": (13.3611, 100.9847)
}


def location_processing_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for geocoding locations"""
    try:
        geocoder = Nominatim(user_agent="fm-station-planner")
        llm_client = OpenRouterClient()

        requirements = state.get("requirements", {})
        province = requirements.get("location", {}).get("province")

        if not province:
            # Default to Bangkok
            coordinates = {"lat": 13.7563, "lon": 100.5018, "name": "Bangkok"}
            return {"location_coords": coordinates}

        # Try to get coordinates
        coordinates = None

        # Check local database first
        if province in THAI_PROVINCES:
            lat, lon = THAI_PROVINCES[province]
            coordinates = {"lat": lat, "lon": lon, "name": province}
        else:
            # Try geocoding with English translation
            try:
                # Use LLM to translate Thai to English for geocoding
                english_name = llm_client.complete(
                    f"Translate this Thai province name to English: {province}. Return ONLY the English name.",
                    task_type="simple_tasks"
                ).strip()

                location = geocoder.geocode(f"{english_name}, Thailand")
                if location:
                    coordinates = {
                        "lat": location.latitude,
                        "lon": location.longitude,
                        "name": province
                    }
            except Exception as e:
                logger.error(f"Geocoding failed: {e}")

        # Fallback to Bangkok if geocoding fails
        if not coordinates:
            coordinates = {"lat": 13.7563, "lon": 100.5018, "name": "Bangkok"}
            logger.warning(f"Could not geocode {province}, using Bangkok as default")

        logger.info(f"Location coordinates: {coordinates}")

        return {"location_coords": coordinates}

    except Exception as e:
        logger.error(f"Location processing error: {e}")
        return {"errors": [f"Location processing failed: {str(e)}"]}

def database_query_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for querying FM station database"""
    try:
        db = StationDatabase()

        requirements = state.get("requirements", {})
        coordinates = state.get("location_coords", {})

        # Build search parameters
        search_params = {
            "province": requirements.get("location", {}).get("province"),
            "district": requirements.get("location", {}).get("district"),
            "radius_km": 50  # Default search radius
        }

        # Get current location - prioritize real GPS coordinates over processed location
        current_location = state.get("current_location")

        # If no real GPS coordinates, fall back to processed location coordinates
        if not current_location and coordinates:
            current_location = (coordinates.get("lat"), coordinates.get("lon"))

        # Search stations
        stations = db.search_stations(search_params, current_location)

        # Limit to requested count
        station_count = requirements.get("station_count", 10)
        stations = stations[:station_count]

        logger.info(f"Found {len(stations)} stations matching criteria")

        return {"stations": stations}

    except Exception as e:
        logger.error(f"Database query error: {e}")
        return {"errors": [f"Database query failed: {str(e)}"]}

def route_planning_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for optimizing inspection routes"""
    try:
        stations = state.get("stations", [])
        requirements = state.get("requirements", {})
        start_location = state.get("location_coords", {})

        if not stations:
            logger.warning("No stations found for routing")
            return {"route_info": {}, "stations_ordered": []}

        # Prepare constraints
        constraints = {
            "max_time_minutes": requirements.get("time_constraint_minutes", 120),
            "start_location": start_location,
            "inspection_time": Config.DEFAULT_INSPECTION_TIME_MINUTES
        }

        # Use hybrid approach: AI suggestion + algorithmic optimization
        if len(stations) > 5 and requirements.get("needs_route"):
            # Use AI for complex routing
            llm_client = OpenRouterClient()
            optimal_order = llm_client.optimize_route_with_ai(stations, constraints)
        else:
            # Simple nearest neighbor for small sets
            optimal_order = _nearest_neighbor_route(stations, start_location)

        # Calculate route details
        route_info = _calculate_route_info(stations, optimal_order, start_location)

        # Check time constraints
        total_minutes = route_info["total_time_minutes"]
        max_time = constraints["max_time_minutes"]

        if max_time and total_minutes > max_time:
            # Trim route to fit time constraint
            route_info = _trim_route_to_fit_time(
                stations, optimal_order, start_location, max_time
            )
            optimal_order = route_info.get("trimmed_order", optimal_order)

        stations_ordered = [stations[i] for i in optimal_order if i < len(stations)]

        logger.info(f"Route planned with {len(stations_ordered)} stations")

        return {
            "route_info": route_info,
            "stations_ordered": stations_ordered
        }

    except Exception as e:
        logger.error(f"Route planning error: {e}")
        return {"errors": [f"Route planning failed: {str(e)}"]}


def _nearest_neighbor_route(stations: List[Dict], start_location: Dict) -> List[int]:
    """Simple nearest neighbor algorithm"""
    if not stations:
        return []

    from haversine import haversine

    unvisited = list(range(len(stations)))
    route = []
    current_pos = (start_location.get("lat", 13.7563),
                  start_location.get("lon", 100.5018))

    while unvisited:
        # Find nearest unvisited station
        nearest_idx = None
        min_distance = float('inf')

        for idx in unvisited:
            station = stations[idx]
            if station.get("latitude") and station.get("longitude"):
                station_pos = (station["latitude"], station["longitude"])
                distance = haversine(current_pos, station_pos)

                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx

        if nearest_idx is not None:
            route.append(nearest_idx)
            unvisited.remove(nearest_idx)
            station = stations[nearest_idx]
            current_pos = (station["latitude"], station["longitude"])
        else:
            # Add remaining stations
            route.extend(unvisited)
            break

    return route


def _calculate_route_info(stations: List[Dict], order: List[int], start_location: Dict) -> Dict:
    """Calculate detailed route information"""
    from haversine import haversine

    total_distance = 0
    total_time = 0
    segments = []

    current_pos = (start_location.get("lat", 13.7563),
                  start_location.get("lon", 100.5018))

    for i, station_idx in enumerate(order):
        if station_idx >= len(stations):
            continue
        station = stations[station_idx]
        if station.get("latitude") and station.get("longitude"):
            station_pos = (station["latitude"], station["longitude"])
            distance = haversine(current_pos, station_pos)

            # Calculate travel time (assuming average speed)
            travel_time = (distance / Config.DEFAULT_SPEED_KMH) * 60

            segments.append({
                "station_index": station_idx,
                "distance_km": round(distance, 2),
                "travel_time_minutes": round(travel_time, 1),
                "inspection_time_minutes": Config.DEFAULT_INSPECTION_TIME_MINUTES
            })

            total_distance += distance
            total_time += travel_time + Config.DEFAULT_INSPECTION_TIME_MINUTES
            current_pos = station_pos

    return {
        "total_distance_km": round(total_distance, 2),
        "total_time_minutes": round(total_time, 1),
        "total_travel_time_minutes": round(total_time - len(order) * Config.DEFAULT_INSPECTION_TIME_MINUTES, 1),
        "total_inspection_time_minutes": len(order) * Config.DEFAULT_INSPECTION_TIME_MINUTES,
        "segments": segments
    }


def _trim_route_to_fit_time(stations: List[Dict], order: List[int], start_location: Dict, max_time: float) -> Dict:
    """Trim route to fit within time constraint"""
    from haversine import haversine

    current_pos = (start_location.get("lat", 13.7563),
                  start_location.get("lon", 100.5018))
    total_time = 0
    trimmed_order = []
    segments = []
    total_distance = 0

    for station_idx in order:
        if station_idx >= len(stations):
            continue
        station = stations[station_idx]
        if station.get("latitude") and station.get("longitude"):
            station_pos = (station["latitude"], station["longitude"])
            distance = haversine(current_pos, station_pos)
            travel_time = (distance / Config.DEFAULT_SPEED_KMH) * 60

            # Check if adding this station exceeds time limit
            station_time = travel_time + Config.DEFAULT_INSPECTION_TIME_MINUTES
            if total_time + station_time > max_time:
                break

            segments.append({
                "station_index": station_idx,
                "distance_km": round(distance, 2),
                "travel_time_minutes": round(travel_time, 1),
                "inspection_time_minutes": Config.DEFAULT_INSPECTION_TIME_MINUTES
            })

            trimmed_order.append(station_idx)
            total_time += station_time
            total_distance += distance
            current_pos = station_pos

    return {
        "total_distance_km": round(total_distance, 2),
        "total_time_minutes": round(total_time, 1),
        "total_travel_time_minutes": round(total_time - len(trimmed_order) * Config.DEFAULT_INSPECTION_TIME_MINUTES, 1),
        "total_inspection_time_minutes": len(trimmed_order) * Config.DEFAULT_INSPECTION_TIME_MINUTES,
        "segments": segments,
        "stations_trimmed": len(order) - len(trimmed_order),
        "trimmed_order": trimmed_order
    }

def plan_evaluation_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for evaluating and optimizing the inspection plan"""
    try:
        stations = state.get("stations", [])
        current_location = state.get("current_location")
        route_info = state.get("route_info", {})

        if not stations:
            logger.info("No stations to evaluate")
            return {"plan_evaluation": {"is_optimal": True, "score": 100, "suggestions": []}}

        # Use start_location if no current_location
        if not current_location:
            start_location_dict = state.get("start_location", {})
            if start_location_dict.get("lat") and start_location_dict.get("lon"):
                current_location = (start_location_dict["lat"], start_location_dict["lon"])
            else:
                # Default to Bangkok coordinates if nothing available
                current_location = (13.7563, 100.5018)

        logger.info(f"Evaluating plan with {len(stations)} stations from location {current_location}")

        # Import and use the plan evaluator
        from plan_evaluator import PlanEvaluationAgent

        evaluator = PlanEvaluationAgent()
        evaluation = evaluator.evaluate_plan(stations, current_location, route_info)

        logger.info(f"Plan evaluation completed. Score: {evaluation.get('score', 0)}/100, Optimal: {evaluation.get('is_optimal', False)}")

        return {"plan_evaluation": evaluation}

    except Exception as e:
        logger.error(f"Plan evaluation error: {e}")
        return {"plan_evaluation": {"is_optimal": True, "score": 50, "suggestions": [], "error": str(e)}}

def response_generation_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for generating Thai language responses"""
    try:
        llm_client = OpenRouterClient()

        stations = state.get("stations_ordered", [])
        route_info = state.get("route_info", {})
        requirements = state.get("requirements", {})
        plan_evaluation = state.get("plan_evaluation", {})

        if not stations:
            response = "Sorry, no FM stations found in the specified area. Please try searching in a different area."
        else:
            # Generate English response
            response = llm_client.generate_english_response(
                stations,
                route_info,
                requirements.get("original_text", ""),
                plan_evaluation  # Include plan evaluation in response
            )

            # Add plan evaluation summary
            if plan_evaluation and plan_evaluation.get("score") is not None:
                score = plan_evaluation.get("score", 0)
                is_optimal = plan_evaluation.get("is_optimal", False)
                ai_eval = plan_evaluation.get("ai_evaluation", "")
                suggestions = plan_evaluation.get("optimization_suggestions", [])

                response += f"\n\n**Route Analysis:**"
                response += f"\n• Route Efficiency Score: {score}/100"
                response += f"\n• Route Status: {'✅ Optimal' if is_optimal else '⚠️ Can be optimized'}"

                if ai_eval:
                    response += f"\n• Expert Analysis: {ai_eval}"

                if suggestions:
                    response += f"\n• Optimization Tips:"
                    for suggestion in suggestions[:3]:  # Show top 3 suggestions
                        response += f"\n  - {suggestion}"

            # Add cost information
            total_cost = llm_client.get_total_cost()
            response += f"\n\nAPI Cost: ${total_cost:.4f}"

        logger.info("Generated response")

        return {"final_response": response}

    except Exception as e:
        logger.error(f"Response generation error: {e}")
        return {"errors": [f"Response generation failed: {str(e)}"]}


def should_continue_after_stations(state: FMStationState) -> str:
    """Conditional edge function to determine next step after finding stations"""
    stations = state.get("stations", [])
    requirements = state.get("requirements", {})

    if not stations:
        return "response"  # Go directly to response generation if no stations found

    if len(stations) > 1 or requirements.get("needs_route"):
        return "routing"  # Need route planning
    else:
        # For single station or no route needed, set up minimal data and go to response
        return "response"


def check_for_errors(state: FMStationState) -> str:
    """Check if there are any accumulated errors"""
    errors = state.get("errors", [])
    if errors:
        return "error_response"
    return "continue"


def location_based_planning_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for real-time location-based inspection planning"""
    try:
        location_tool = LocationTool()
        current_location = state.get("current_location")
        requirements = state.get("requirements", {})

        if not current_location:
            return {"errors": ["Current location not provided for location-based planning"]}

        # Extract location filters from requirements
        location_info = requirements.get("location", {})
        province = location_info.get("province")
        district = location_info.get("district")
        max_stations = requirements.get("station_count", 5)

        # Get location-based inspection plan
        plan = location_tool.get_inspection_plan_by_location(
            current_location=current_location,
            max_stations=max_stations,
            max_radius_km=50,  # 50km radius
            district=district,
            province=province
        )

        if plan.get("success"):
            logger.info(f"Generated location-based plan with {len(plan.get('stations', []))} stations")

            # Format the response
            formatted_response = location_tool.format_inspection_plan(plan)

            return {
                "location_based_plan": plan,
                "stations_ordered": plan.get("stations", []),
                "final_response": formatted_response
            }
        else:
            error_msg = plan.get("message", "Failed to generate location-based plan")
            return {"errors": [error_msg]}

    except Exception as e:
        logger.error(f"Location-based planning error: {e}")
        return {"errors": [f"Location-based planning failed: {str(e)}"]}


def step_by_step_planning_node(state: FMStationState) -> Dict[str, Any]:
    """Step-by-step agent: 1) Find province 2) Find nearest station 3) Continue to next nearest"""
    try:
        db = StationDatabase()
        llm_client = OpenRouterClient()

        current_location = state.get("current_location")
        requirements = state.get("requirements", {})
        station_count = requirements.get("station_count", 5)
        visited_station_ids = state.get("visited_station_ids", [])

        if not current_location:
            return {"errors": ["Current location is required for step-by-step planning"]}

        logger.info(f"Step-by-step planning: Finding {station_count} stations from {current_location}")

        # Step 1: Detect province from user's location
        detected_province = db._detect_province_from_gps(current_location)
        if not detected_province:
            return {"errors": ["Could not determine province from current location"]}

        logger.info(f"Step 1: User is in province: {detected_province}")

        # Step 2: Find stations one by one using nearest-neighbor approach
        stations_sequence = []
        current_pos = current_location

        for step in range(station_count):
            logger.info(f"Step {step + 2}: Finding nearest station from {current_pos}")

            nearest_station = db.get_nearest_station(current_pos, visited_station_ids)

            if not nearest_station:
                logger.info(f"No more available stations found after {len(stations_sequence)} stations")
                break

            # Add to sequence
            stations_sequence.append(nearest_station)
            visited_station_ids.append(str(nearest_station.get('id_fm')))

            # Update current position to the station we just added
            if nearest_station.get('lat') and nearest_station.get('long'):
                current_pos = (nearest_station['lat'], nearest_station['long'])

            logger.info(f"Added station: {nearest_station.get('name')} "
                       f"at {nearest_station.get('distance_km', 0)}km")

        # Calculate total route information
        route_info = _calculate_route_info_step_by_step(stations_sequence, current_location)

        logger.info(f"Step-by-step planning completed: {len(stations_sequence)} stations, "
                   f"Total distance: {route_info.get('total_distance_km', 0)}km")

        return {
            "stations": stations_sequence,
            "stations_ordered": stations_sequence,
            "route_info": route_info,
            "visited_station_ids": visited_station_ids,
            "step_by_step_mode": True
        }

    except Exception as e:
        logger.error(f"Step-by-step planning error: {e}")
        return {"errors": [f"Step-by-step planning failed: {str(e)}"]}


def _calculate_route_info_step_by_step(stations: List[Dict], start_location: Tuple[float, float]) -> Dict:
    """Calculate route info for step-by-step sequence"""
    from haversine import haversine

    if not stations:
        return {"total_distance_km": 0, "total_time_minutes": 0, "stations": []}

    total_distance = 0
    total_time = 0
    current_pos = start_location

    for i, station in enumerate(stations):
        if station.get('lat') and station.get('long'):
            station_pos = (station['lat'], station['long'])
            distance = haversine(current_pos, station_pos)
            travel_time = (distance / Config.DEFAULT_SPEED_KMH) * 60

            total_distance += distance
            total_time += travel_time + Config.DEFAULT_INSPECTION_TIME_MINUTES

            current_pos = station_pos

    return {
        "total_distance_km": round(total_distance, 2),
        "total_time_minutes": round(total_time, 1),
        "stations": len(stations),
        "approach": "step_by_step_nearest_neighbor"
    }


def detect_location_based_request(state: FMStationState) -> str:
    """Conditional edge to detect if this is a location-based request"""
    user_input = state.get("user_input", "").lower()
    current_location = state.get("current_location")

    # Check for location-based keywords
    location_keywords = [
        "nearest", "closest", "near me", "current location",
        "from here", "uninspected", "not inspected", "my location"
    ]

    is_location_request = any(keyword in user_input for keyword in location_keywords)

    if is_location_request and current_location:
        return "location_based"
    else:
        return "standard"


def multi_day_planning_node(state: FMStationState) -> Dict[str, Any]:
    """Multi-day planning with home return requirements"""
    try:
        from multi_day_planner import MultiDayPlanner

        user_input = state.get("user_input")
        planner = MultiDayPlanner()

        result = planner.plan_multi_day_inspection(user_input)

        return {
            "final_response": result
        }

    except Exception as e:
        logger.error(f"Multi-day planning error: {e}")
        return {"errors": [f"Multi-day planning failed: {str(e)}"]}


def detect_step_by_step_request(state: FMStationState) -> str:
    """Conditional edge to detect request type"""
    user_input = state.get("user_input", "").lower()
    current_location = state.get("current_location")

    # Check for multi-day keywords first
    multi_day_keywords = [
        "2 day", "two day", "1 day", "one day",
        "day make", "go 2 day", "go 1 day"
    ]

    is_multi_day = any(keyword in user_input for keyword in multi_day_keywords)

    if is_multi_day:
        return "multi_day"

    # Keywords that suggest step-by-step approach
    step_by_step_keywords = [
        "step by step", "one by one", "nearest", "closest",
        "make plan", "plan for", "station for me"
    ]

    is_step_by_step = any(keyword in user_input for keyword in step_by_step_keywords)

    if is_step_by_step and current_location:
        return "step_by_step"
    else:
        return "standard"


def error_response_node(state: FMStationState) -> Dict[str, Any]:
    """Generate error response for accumulated errors"""
    errors = state.get("errors", [])
    error_message = "Sorry, errors occurred during processing:\n" + "\n".join(f"• {error}" for error in errors)

    return {"final_response": error_message}