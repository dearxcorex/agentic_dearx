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
    final_response: str  # Final response
    errors: Annotated[List[str], operator.add]  # Accumulated errors

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

        # Get current location
        current_location = None
        if coordinates:
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
            # Generate English response
            response = llm_client.generate_english_response(
                stations,
                route_info,
                requirements.get("original_text", "")
            )

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


def error_response_node(state: FMStationState) -> Dict[str, Any]:
    """Generate error response for accumulated errors"""
    errors = state.get("errors", [])
    error_message = "Sorry, errors occurred during processing:\n" + "\n".join(f"• {error}" for error in errors)

    return {"final_response": error_message}