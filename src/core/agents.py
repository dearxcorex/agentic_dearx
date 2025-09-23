"""LangGraph nodes for FM Station Planning"""

from typing import Dict, List, Optional, Tuple, Any, Annotated, Union
from typing_extensions import TypedDict
import json
import re
from geopy.geocoders import Nominatim
from ..services.openrouter_client import OpenRouterClient
from ..database.database import StationDatabase
from ..utils.location_tool import LocationTool
from ..config.config import Config
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
        days = None

        # Look for day constraints first
        if "day" in user_input.lower():
            day_matches = re.findall(r'(\d+)\s*day', user_input.lower())
            if day_matches:
                days = int(day_matches[0])

        # Look for time constraints (only if not day-related)
        if len(numbers) >= 2 and not days:
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
            "days": days,
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
    "นครราชสีมา": (14.9799, 102.0977),
    "บุรีรัมย์": (14.9930, 103.1029),
    "กรุงเทพมหานคร": (13.7563, 100.5018),
    "เชียงใหม่": (18.7883, 98.9853),
    "ภูเก็ต": (7.8804, 98.3923),
    "ขอนแก่น": (16.4322, 102.8236),
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

        # Prepare constraints (no time limits)
        constraints = {
            "start_location": start_location,
            "inspection_time": Config.DEFAULT_INSPECTION_TIME_MINUTES
        }

        # Use district-based routing by default for efficiency
        logger.info("Using district-based routing to prioritize areas with more stations")
        optimal_order = _district_based_route(stations, start_location)

        # Simple routing only - no AI optimization

        # Calculate route details
        route_info = _calculate_route_info(stations, optimal_order, start_location)

        # No more time constraint trimming - user gets all requested stations
        # total_minutes = route_info["total_time_minutes"]
        # max_time = constraints["max_time_minutes"]

        stations_ordered = [stations[i] for i in optimal_order if i < len(stations)]

        logger.info(f"Route planned with {len(stations_ordered)} stations")

        return {
            "route_info": route_info,
            "stations_ordered": stations_ordered
        }

    except Exception as e:
        logger.error(f"Route planning error: {e}")
        return {"errors": [f"Route planning failed: {str(e)}"]}


def _group_stations_by_district(stations: List[Dict]) -> Dict[str, List[int]]:
    """Group stations by district and count stations per district"""
    district_groups = {}

    for idx, station in enumerate(stations):
        district = station.get("district", "Unknown")
        if district not in district_groups:
            district_groups[district] = []
        district_groups[district].append(idx)

    # Sort districts by number of stations (descending)
    sorted_districts = dict(sorted(district_groups.items(),
                                 key=lambda x: len(x[1]),
                                 reverse=True))

    logger.info(f"Districts found: {[(district, len(stations)) for district, stations in sorted_districts.items()]}")

    return sorted_districts

def _district_based_route(stations: List[Dict], start_location: Dict) -> List[int]:
    """District-based routing: prioritize districts with most stations"""
    if not stations:
        return []

    from haversine import haversine

    # Group stations by district
    district_groups = _group_stations_by_district(stations)

    route = []
    current_pos = (start_location.get("lat", 13.7563),
                  start_location.get("lon", 100.5018))

    # Process each district in order of station count (highest first)
    for district, station_indices in district_groups.items():
        logger.info(f"Processing district '{district}' with {len(station_indices)} stations")

        # Within each district, use nearest neighbor
        unvisited_in_district = station_indices.copy()

        while unvisited_in_district:
            nearest_idx = None
            min_distance = float('inf')

            for idx in unvisited_in_district:
                station = stations[idx]
                if station.get("latitude") and station.get("longitude"):
                    station_pos = (station["latitude"], station["longitude"])
                    distance = haversine(current_pos, station_pos)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_idx = idx

            if nearest_idx is not None:
                route.append(nearest_idx)
                unvisited_in_district.remove(nearest_idx)
                station = stations[nearest_idx]
                current_pos = (station["latitude"], station["longitude"])
            else:
                # Add remaining stations in district
                route.extend(unvisited_in_district)
                break

    return route

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
    """Calculate detailed route information with same-district optimization"""
    from haversine import haversine

    total_distance = 0
    total_time = 0
    segments = []

    current_pos = (start_location.get("lat", 13.7563),
                  start_location.get("lon", 100.5018))
    current_district = None

    for i, station_idx in enumerate(order):
        if station_idx >= len(stations):
            continue
        station = stations[station_idx]
        if station.get("latitude") and station.get("longitude"):
            station_pos = (station["latitude"], station["longitude"])
            station_district = station.get("district", "Unknown")

            # Optimize: Skip distance calculation if in same district as previous station
            if i > 0 and current_district == station_district and current_district != "Unknown":
                # Use minimal distance for same district (stations are already nearest)
                distance = 0.5  # Assume 0.5km between stations in same district
                travel_time = 1.0  # Assume 1 minute travel time
                logger.debug(f"Same district optimization: {station_district} - using minimal distance")
            else:
                # Calculate actual distance for first station or different district
                distance = haversine(current_pos, station_pos)
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
            current_district = station_district

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
    """Simple node that just passes through - no evaluation needed"""
    return {"plan_evaluation": {"simple_mode": True}}

def response_generation_node(state: FMStationState) -> Dict[str, Any]:
    """LangGraph node for generating Thai language responses"""
    try:
        llm_client = OpenRouterClient()

        stations = state.get("stations_ordered", [])
        route_info = state.get("route_info", {})
        requirements = state.get("requirements", {})

        if not stations:
            response = "Sorry, no FM stations found in the specified area. Please try searching in a different area."
        else:
            # Generate district summary first
            district_summary = _generate_district_summary(stations)

            # Generate English response
            response = llm_client.generate_english_response(
                stations,
                route_info,
                requirements.get("original_text", ""),
                {}  # No plan evaluation
            )

            # Add district analysis
            if district_summary:
                response += f"\n\n**District Analysis:**"
                response += f"\n{district_summary}"

            # Add basic distance/time warning if needed
            if route_info:
                total_distance = route_info.get("total_distance_km", 0)
                total_time = route_info.get("total_time_minutes", 0)

                if total_distance > 300 or total_time > 480:  # 8 hours
                    response += f"\n\n⚠️ **Notice:**"
                    if total_distance > 300:
                        response += f"\n• Total distance: {total_distance:.1f}km (above 300km threshold)"
                    if total_time > 480:
                        response += f"\n• Total time: {total_time/60:.1f} hours (above 8 hour threshold)"

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
    """Calculate route info for step-by-step sequence with same-district optimization"""
    from haversine import haversine

    if not stations:
        return {"total_distance_km": 0, "total_time_minutes": 0, "stations": []}

    total_distance = 0
    total_time = 0
    current_pos = start_location
    current_district = None

    for i, station in enumerate(stations):
        if station.get('lat') and station.get('long'):
            station_pos = (station['lat'], station['long'])
            station_district = station.get("district", "Unknown")

            # Optimize: Skip distance calculation if in same district as previous station
            if i > 0 and current_district == station_district and current_district != "Unknown":
                # Use minimal distance for same district (stations are already nearest)
                distance = 0.5  # Assume 0.5km between stations in same district
                travel_time = 1.0  # Assume 1 minute travel time
                logger.debug(f"Step-by-step same district optimization: {station_district}")
            else:
                # Calculate actual distance for first station or different district
                distance = haversine(current_pos, station_pos)
                travel_time = (distance / Config.DEFAULT_SPEED_KMH) * 60

            total_distance += distance
            total_time += travel_time + Config.DEFAULT_INSPECTION_TIME_MINUTES
            current_pos = station_pos
            current_district = station_district

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
        from .multi_day_planner import MultiDayPlanner

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
        "in 2 day", "in 1 day", "for 2 day", "for 1 day",
        "day make", "go 2 day", "go 1 day", "2day", "1day"
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

def _generate_district_summary(stations: List[Dict]) -> str:
    """Generate a summary of stations by district"""
    if not stations:
        return ""

    # Group stations by district
    district_counts = {}
    for station in stations:
        district = station.get("district", "Unknown")
        district_counts[district] = district_counts.get(district, 0) + 1

    # Sort by count (descending)
    sorted_districts = sorted(district_counts.items(), key=lambda x: x[1], reverse=True)

    summary_lines = []
    summary_lines.append("📍 **Stations grouped by district (prioritized by station density):**")

    for district, count in sorted_districts:
        percentage = (count / len(stations)) * 100
        summary_lines.append(f"• **{district}**: {count} stations ({percentage:.1f}%)")

    summary_lines.append(f"\n🎯 **Strategy**: Prioritizing districts with more stations for efficiency")

    return "\n".join(summary_lines)