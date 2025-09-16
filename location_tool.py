"""
Real-time location tool for FM Station inspection planning
"""

from typing import Dict, List, Optional, Tuple, Any
from haversine import haversine, Unit
from database import StationDatabase
import logging
import json

logger = logging.getLogger(__name__)

class LocationTool:
    """Tool for real-time location access and distance calculations"""

    def __init__(self):
        self.db = StationDatabase()

    def get_current_location(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict[str, float]]:
        """
        Get current GPS location

        Args:
            lat: Latitude from external source (e.g., Telegram bot)
            lon: Longitude from external source (e.g., Telegram bot)

        Returns:
            Dictionary with lat/lon or None if not available
        """
        if lat is not None and lon is not None:
            return {"latitude": lat, "longitude": lon}

        # For mobile/bot integration, location will be provided externally
        return None

    def calculate_distance(self,
                          location1: Tuple[float, float],
                          location2: Tuple[float, float]) -> float:
        """Calculate distance between two GPS coordinates in kilometers"""
        return haversine(location1, location2, unit=Unit.KILOMETERS)

    def find_nearest_uninspected_stations(self,
                                        current_location: Tuple[float, float],
                                        district: Optional[str] = None,
                                        province: Optional[str] = None,
                                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find nearest stations that haven't been inspected yet

        Args:
            current_location: (lat, lon) tuple of current position
            district: Optional district filter
            province: Optional province filter
            limit: Maximum number of stations to return
        """
        try:
            # Get all uninspected stations
            stations = self.db.get_uninspected_stations(
                district=district,
                province=province
            )

            if not stations:
                logger.warning("No uninspected stations found")
                return []

            # Calculate distances and add to each station
            for station in stations:
                if station.get("latitude") and station.get("longitude"):
                    station_coords = (station["latitude"], station["longitude"])
                    distance = self.calculate_distance(current_location, station_coords)
                    station["distance_km"] = round(distance, 2)
                else:
                    station["distance_km"] = float('inf')

            # Sort by distance and limit results
            stations.sort(key=lambda x: x.get("distance_km", float('inf')))
            return stations[:limit]

        except Exception as e:
            logger.error(f"Error finding nearest uninspected stations: {e}")
            return []

    def find_stations_within_radius(self,
                                   current_location: Tuple[float, float],
                                   radius_km: float = 20,
                                   district: Optional[str] = None,
                                   province: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find uninspected stations within a specific radius

        Args:
            current_location: (lat, lon) tuple of current position
            radius_km: Search radius in kilometers
            district: Optional district filter
            province: Optional province filter
        """
        try:
            # Get all uninspected stations
            stations = self.db.get_uninspected_stations(
                district=district,
                province=province
            )

            nearby_stations = []
            for station in stations:
                if station.get("latitude") and station.get("longitude"):
                    station_coords = (station["latitude"], station["longitude"])
                    distance = self.calculate_distance(current_location, station_coords)

                    if distance <= radius_km:
                        station["distance_km"] = round(distance, 2)
                        nearby_stations.append(station)

            # Sort by distance
            nearby_stations.sort(key=lambda x: x.get("distance_km", 0))
            return nearby_stations

        except Exception as e:
            logger.error(f"Error finding stations within radius: {e}")
            return []

    def get_inspection_plan_by_location(self,
                                      current_location: Tuple[float, float],
                                      max_stations: int = 5,
                                      max_radius_km: float = 50,
                                      district: Optional[str] = None,
                                      province: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate an inspection plan based on current location

        Args:
            current_location: (lat, lon) tuple of current position
            max_stations: Maximum number of stations to include
            max_radius_km: Maximum search radius
            district: Optional district filter
            province: Optional province filter
        """
        try:
            # Find nearest uninspected stations
            nearest_stations = self.find_nearest_uninspected_stations(
                current_location=current_location,
                district=district,
                province=province,
                limit=max_stations * 2  # Get more options to filter by radius
            )

            # Filter by radius
            stations_in_range = [
                station for station in nearest_stations
                if station.get("distance_km", float('inf')) <= max_radius_km
            ][:max_stations]

            if not stations_in_range:
                return {
                    "success": False,
                    "message": f"No uninspected stations found within {max_radius_km}km",
                    "stations": [],
                    "total_distance": 0,
                    "estimated_time": 0
                }

            # Calculate total travel distance (simple route)
            total_distance = 0
            prev_location = current_location

            for station in stations_in_range:
                if station.get("latitude") and station.get("longitude"):
                    station_coords = (station["latitude"], station["longitude"])
                    segment_distance = self.calculate_distance(prev_location, station_coords)
                    total_distance += segment_distance
                    prev_location = station_coords

            # Estimate time (40 km/h average speed + 10 min inspection per station)
            travel_time_hours = total_distance / 40
            inspection_time_hours = len(stations_in_range) * (10 / 60)  # 10 min per station
            total_time_hours = travel_time_hours + inspection_time_hours

            return {
                "success": True,
                "message": f"Found {len(stations_in_range)} uninspected stations",
                "stations": stations_in_range,
                "total_distance_km": round(total_distance, 2),
                "estimated_time_hours": round(total_time_hours, 2),
                "estimated_time_minutes": round(total_time_hours * 60, 0),
                "current_location": {
                    "lat": current_location[0],
                    "lon": current_location[1]
                }
            }

        except Exception as e:
            logger.error(f"Error generating location-based inspection plan: {e}")
            return {
                "success": False,
                "message": f"Error generating plan: {str(e)}",
                "stations": [],
                "total_distance": 0,
                "estimated_time": 0
            }

    def format_inspection_plan(self, plan: Dict[str, Any]) -> str:
        """Format inspection plan into readable text"""
        if not plan.get("success"):
            return plan.get("message", "Failed to generate inspection plan")

        stations = plan.get("stations", [])
        if not stations:
            return "No stations found for inspection"

        response = f"📍 **Inspection Plan from Current Location**\n\n"
        response += f"Found {len(stations)} uninspected stations:\n\n"

        for i, station in enumerate(stations, 1):
            response += f"{i}. **{station.get('station_name', 'Unknown Station')}**\n"
            response += f"   - Frequency: {station.get('frequency', 'N/A')} MHz\n"
            response += f"   - Location: {station.get('district', 'N/A')}, {station.get('province', 'N/A')}\n"
            response += f"   - Distance: {station.get('distance_km', 'N/A')} km from current location\n"
            response += f"   - Status: Not yet inspected\n\n"

        response += f"**Summary:**\n"
        response += f"- Total Distance: {plan.get('total_distance_km', 0)} km\n"
        response += f"- Estimated Time: {plan.get('estimated_time_hours', 0)} hours "
        response += f"({plan.get('estimated_time_minutes', 0)} minutes)\n"
        response += f"- Stations to inspect: {len(stations)}\n"

        return response