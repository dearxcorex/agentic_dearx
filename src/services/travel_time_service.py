"""
Travel Time Service using free routing APIs for accurate travel time calculations
"""

import requests
import logging
from typing import Tuple, Dict, Any, Optional
from haversine import haversine, Unit

logger = logging.getLogger(__name__)

class TravelTimeService:
    """Service for accurate travel time calculations using real routing APIs"""

    def __init__(self):
        # OSRM server (free, no API key needed)
        self.osrm_base_url = "http://router.project-osrm.org/route/v1/driving"

        # Fallback to simple distance calculation
        self.fallback_speed_kmh = 45  # More realistic average speed

    def get_travel_time_osrm(self,
                            origin: Tuple[float, float],
                            destination: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Get travel time using OSRM (OpenStreetMap Routing Machine)

        Args:
            origin: (lat, lon) tuple of starting point
            destination: (lat, lon) tuple of ending point

        Returns:
            Dictionary with duration (seconds), distance (meters), and route info
        """
        try:
            # OSRM expects lon,lat format
            coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            url = f"{self.osrm_base_url}/{coordinates}"

            params = {
                'overview': 'false',  # Don't need full geometry
                'alternatives': 'false',  # Just the best route
                'steps': 'false'  # Don't need turn-by-turn
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get('code') == 'Ok' and data.get('routes'):
                route = data['routes'][0]
                return {
                    'duration_seconds': route['duration'],
                    'duration_minutes': round(route['duration'] / 60, 1),
                    'distance_meters': route['distance'],
                    'distance_km': round(route['distance'] / 1000, 2),
                    'source': 'osrm'
                }
            else:
                logger.warning(f"OSRM routing failed: {data.get('message', 'Unknown error')}")
                return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"OSRM API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling OSRM API: {e}")
            return None

    def get_travel_time_fallback(self,
                               origin: Tuple[float, float],
                               destination: Tuple[float, float]) -> Dict[str, Any]:
        """
        Fallback method using straight-line distance and average speed

        Args:
            origin: (lat, lon) tuple of starting point
            destination: (lat, lon) tuple of ending point

        Returns:
            Dictionary with estimated duration and distance
        """
        try:
            # Calculate straight-line distance
            distance_km = haversine(origin, destination, unit=Unit.KILOMETERS)

            # Add 25% to account for non-straight roads
            road_distance_km = distance_km * 1.25

            # Calculate time based on average speed
            duration_hours = road_distance_km / self.fallback_speed_kmh
            duration_minutes = duration_hours * 60

            return {
                'duration_seconds': round(duration_minutes * 60),
                'duration_minutes': round(duration_minutes, 1),
                'distance_meters': round(road_distance_km * 1000),
                'distance_km': round(road_distance_km, 2),
                'source': 'fallback'
            }

        except Exception as e:
            logger.error(f"Error in fallback calculation: {e}")
            # Return basic estimates
            return {
                'duration_seconds': 1800,  # 30 minutes default
                'duration_minutes': 30.0,
                'distance_meters': 20000,  # 20km default
                'distance_km': 20.0,
                'source': 'default'
            }

    def get_travel_time(self,
                       origin: Tuple[float, float],
                       destination: Tuple[float, float]) -> Dict[str, Any]:
        """
        Get travel time using the best available method

        Args:
            origin: (lat, lon) tuple of starting point
            destination: (lat, lon) tuple of ending point

        Returns:
            Dictionary with duration, distance, and source information
        """
        # First try OSRM
        result = self.get_travel_time_osrm(origin, destination)

        if result is not None:
            logger.debug(f"Using OSRM for travel time calculation")
            return result

        # Fallback to distance-based calculation
        logger.debug(f"Using fallback method for travel time calculation")
        return self.get_travel_time_fallback(origin, destination)

    def get_multi_destination_times(self,
                                  origin: Tuple[float, float],
                                  destinations: list[Tuple[float, float]]) -> list[Dict[str, Any]]:
        """
        Get travel times to multiple destinations

        Args:
            origin: (lat, lon) tuple of starting point
            destinations: List of (lat, lon) tuples for destinations

        Returns:
            List of travel time dictionaries
        """
        results = []

        for i, destination in enumerate(destinations):
            try:
                travel_info = self.get_travel_time(origin, destination)
                travel_info['destination_index'] = i
                results.append(travel_info)
            except Exception as e:
                logger.error(f"Error calculating travel time to destination {i}: {e}")
                # Add default result
                results.append({
                    'duration_seconds': 1800,
                    'duration_minutes': 30.0,
                    'distance_meters': 20000,
                    'distance_km': 20.0,
                    'source': 'error_default',
                    'destination_index': i
                })

        return results

    def optimize_route_order(self,
                           origin: Tuple[float, float],
                           destinations: list[Tuple[float, float]]) -> list[int]:
        """
        Simple nearest-neighbor optimization for visiting multiple destinations

        Args:
            origin: (lat, lon) tuple of starting point
            destinations: List of (lat, lon) tuples for destinations

        Returns:
            List of indices representing the optimized order
        """
        if not destinations:
            return []

        if len(destinations) == 1:
            return [0]

        # Start from origin
        current_location = origin
        remaining_indices = list(range(len(destinations)))
        optimized_order = []

        while remaining_indices:
            # Find nearest unvisited destination
            min_time = float('inf')
            nearest_index = None
            nearest_actual_index = None

            for i, dest_index in enumerate(remaining_indices):
                destination = destinations[dest_index]
                travel_info = self.get_travel_time(current_location, destination)

                if travel_info['duration_minutes'] < min_time:
                    min_time = travel_info['duration_minutes']
                    nearest_index = i
                    nearest_actual_index = dest_index

            # Add nearest destination to route
            if nearest_actual_index is not None:
                optimized_order.append(nearest_actual_index)
                current_location = destinations[nearest_actual_index]
                remaining_indices.pop(nearest_index)

        return optimized_order