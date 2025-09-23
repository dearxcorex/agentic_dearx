"""
Travel Time Service using free routing APIs for accurate travel time calculations
"""

import requests
import logging
import time
import os
from typing import Tuple, Dict, Any, Optional
from haversine import haversine, Unit

class DistanceCache:
    """Cache for storing computed distances to avoid repeated API calls"""

    def __init__(self):
        self.district_to_district_cache = {}  # Cache for district-to-district distances
        self.district_to_home_cache = {}      # Cache for district-to-home distances
        self.same_district_time = 1.0         # Fixed time for same district (minutes)
        self.same_district_distance = 0.5     # Fixed distance for same district (km)

    def get_district_key(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> str:
        """Generate cache key for coordinate pair"""
        return f"{coord1[0]:.4f},{coord1[1]:.4f}-{coord2[0]:.4f},{coord2[1]:.4f}"

    def cache_district_distance(self,
                               coord1: Tuple[float, float],
                               coord2: Tuple[float, float],
                               travel_info: Dict):
        """Cache travel info between districts"""
        key = self.get_district_key(coord1, coord2)
        self.district_to_district_cache[key] = travel_info
        # Also cache reverse direction
        reverse_key = self.get_district_key(coord2, coord1)
        self.district_to_district_cache[reverse_key] = travel_info

    def get_cached_district_distance(self,
                                   coord1: Tuple[float, float],
                                   coord2: Tuple[float, float]) -> Optional[Dict]:
        """Get cached travel info between districts"""
        key = self.get_district_key(coord1, coord2)
        return self.district_to_district_cache.get(key)

    def cache_home_distance(self, district_coord: Tuple[float, float], travel_info: Dict):
        """Cache travel info from district to home"""
        key = f"home-{district_coord[0]:.4f},{district_coord[1]:.4f}"
        self.district_to_home_cache[key] = travel_info

    def get_cached_home_distance(self, district_coord: Tuple[float, float]) -> Optional[Dict]:
        """Get cached travel info from district to home"""
        key = f"home-{district_coord[0]:.4f},{district_coord[1]:.4f}"
        return self.district_to_home_cache.get(key)

    def get_same_district_travel_info(self) -> Dict[str, Any]:
        """Return standard travel info for same district stations"""
        return {
            'duration_seconds': self.same_district_time * 60,
            'duration_minutes': self.same_district_time,
            'distance_meters': self.same_district_distance * 1000,
            'distance_km': self.same_district_distance,
            'source': 'same_district_cache'
        }

logger = logging.getLogger(__name__)

class TravelTimeService:
    """Service for accurate travel time calculations using real routing APIs"""

    def __init__(self):
        # OSRM server (free, no API key needed)
        self.osrm_base_url = "http://router.project-osrm.org/route/v1/driving"

        # OpenRouteService configuration
        self.ors_api_key = os.getenv("OPENROUTESERVICE_API_KEY")
        self.ors_base_url = "https://api.openrouteservice.org/v2/directions/driving-car"

        # Initialize distance cache
        self.cache = DistanceCache()

        # Debug: Check if API key is loaded
        if self.ors_api_key:
            logger.info("OpenRouteService API key loaded successfully")
        else:
            logger.warning("OpenRouteService API key not found in environment variables")

        # Timeout and retry configuration
        self.timeout = 15  # Reduced timeout for faster fallback
        self.max_retries = 1  # Reduced retries to avoid rate limits
        self.retry_delay = 1  # seconds between retries
        self.rate_limit_delay = 3  # seconds to wait for rate limit errors

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
        # OSRM expects lon,lat format
        coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = f"{self.osrm_base_url}/{coordinates}"

        params = {
            'overview': 'false',  # Don't need full geometry
            'alternatives': 'false',  # Just the best route
            'steps': 'false'  # Don't need turn-by-turn
        }

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"OSRM API attempt {attempt + 1}/{self.max_retries}")

                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()

                if data.get('code') == 'Ok' and data.get('routes'):
                    route = data['routes'][0]
                    logger.debug(f"OSRM API successful on attempt {attempt + 1}")
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

            except requests.exceptions.Timeout as e:
                logger.warning(f"OSRM API timeout on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"OSRM API failed after {self.max_retries} attempts due to timeout")
                    return None

            except requests.exceptions.RequestException as e:
                logger.warning(f"OSRM API request failed on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"OSRM API failed after {self.max_retries} attempts")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error calling OSRM API: {e}")
                return None

        return None

    def get_travel_time_ors(self,
                           origin: Tuple[float, float],
                           destination: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Get travel time using OpenRouteService API

        Args:
            origin: (lat, lon) tuple of starting point
            destination: (lat, lon) tuple of ending point

        Returns:
            Dictionary with duration (seconds), distance (meters), and route info
        """
        if not self.ors_api_key:
            logger.warning("OpenRouteService API key not configured - falling back to distance calculation")
            return None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"ORS API attempt {attempt + 1}/{self.max_retries}")

                # ORS expects lon,lat format in coordinates array
                headers = {
                    'Authorization': self.ors_api_key,
                    'Content-Type': 'application/json'
                }

                data = {
                    'coordinates': [
                        [origin[1], origin[0]],      # start: [lon, lat]
                        [destination[1], destination[0]]  # end: [lon, lat]
                    ],
                    'format': 'json'
                }

                response = requests.post(self.ors_base_url, json=data, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                result = response.json()

                if 'routes' in result and len(result['routes']) > 0:
                    route = result['routes'][0]
                    summary = route['summary']

                    logger.debug(f"ORS API successful on attempt {attempt + 1}")
                    return {
                        'duration_seconds': summary['duration'],
                        'duration_minutes': round(summary['duration'] / 60, 1),
                        'distance_meters': summary['distance'],
                        'distance_km': round(summary['distance'] / 1000, 2),
                        'source': 'openrouteservice'
                    }
                else:
                    logger.warning(f"ORS routing failed: No routes found")
                    return None

            except requests.exceptions.Timeout as e:
                logger.warning(f"ORS API timeout on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"ORS API failed after {self.max_retries} attempts due to timeout")
                    return None

            except requests.exceptions.RequestException as e:
                # Handle rate limiting specifically
                if "429" in str(e) or "Too Many Requests" in str(e):
                    logger.warning(f"ORS API rate limit hit on attempt {attempt + 1}: {e}")
                    if attempt < self.max_retries - 1:
                        logger.info(f"Waiting {self.rate_limit_delay} seconds for rate limit...")
                        time.sleep(self.rate_limit_delay)
                        continue
                    else:
                        logger.error(f"ORS API rate limit exceeded after {self.max_retries} attempts - falling back")
                        return None
                else:
                    logger.warning(f"ORS API request failed on attempt {attempt + 1}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logger.error(f"ORS API failed after {self.max_retries} attempts")
                        return None

            except Exception as e:
                logger.error(f"Unexpected error calling ORS API: {e}")
                return None

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

            # Add 35% to account for non-straight roads and better accuracy
            road_distance_km = distance_km * 1.35

            # Calculate time based on average speed (more realistic for Thai roads)
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
                       destination: Tuple[float, float],
                       skip_api: bool = False) -> Dict[str, Any]:
        """
        Get travel time using the best available method

        Args:
            origin: (lat, lon) tuple of starting point
            destination: (lat, lon) tuple of ending point
            skip_api: Skip API calls and use fallback calculation directly

        Returns:
            Dictionary with duration, distance, and source information
        """
        # If explicitly asked to skip API or if we should avoid rate limits
        if skip_api:
            logger.debug(f"Skipping API calls, using fallback distance calculation")
            return self.get_travel_time_fallback(origin, destination)

        # Try OpenRouteService but fallback quickly on rate limits
        if self.ors_api_key:
            result = self.get_travel_time_ors(origin, destination)
            if result is not None:
                logger.debug(f"Using OpenRouteService for travel time calculation")
                return result
            else:
                logger.debug(f"OpenRouteService unavailable (likely rate limited), using fallback calculation")

        # Skip OSRM due to timeout issues - go straight to fallback
        logger.debug(f"Using fallback distance calculation")
        return self.get_travel_time_fallback(origin, destination)

    def get_same_district_travel_time(self) -> Dict[str, Any]:
        """Return minimal travel time for same district stations"""
        return self.cache.get_same_district_travel_info()

    def get_travel_time_with_cache(self,
                                 origin: Tuple[float, float],
                                 destination: Tuple[float, float],
                                 origin_district: str = None,
                                 destination_district: str = None,
                                 home_location: Tuple[float, float] = None) -> Dict[str, Any]:
        """
        Get travel time with smart caching for district-based optimization

        Args:
            origin: (lat, lon) of starting point
            destination: (lat, lon) of ending point
            origin_district: District name of origin (for same-district detection)
            destination_district: District name of destination
            home_location: Home coordinates for caching return times

        Returns:
            Dictionary with duration, distance, and source information
        """
        # Same district optimization - no API calls
        if (origin_district and destination_district and
            origin_district == destination_district and
            origin_district != "Unknown"):
            logger.debug(f"Same district optimization: {origin_district}")
            return self.get_same_district_travel_time()

        # Check cache for district-to-district
        cached = self.cache.get_cached_district_distance(origin, destination)
        if cached:
            logger.debug(f"Using cached district distance")
            return cached

        # Check cache for home distance
        if home_location and destination == home_location:
            cached_home = self.cache.get_cached_home_distance(origin)
            if cached_home:
                logger.debug(f"Using cached home distance")
                return cached_home

        # Make API call and cache result
        travel_info = self.get_travel_time(origin, destination, skip_api=False)

        # Cache the result for future use
        if origin_district != destination_district:
            self.cache.cache_district_distance(origin, destination, travel_info)

        # Cache home distance if applicable
        if home_location and destination == home_location:
            self.cache.cache_home_distance(origin, travel_info)

        return travel_info

    def batch_precompute_district_distances(self,
                                          district_centers: Dict[str, Tuple[float, float]],
                                          home_location: Tuple[float, float] = None):
        """
        Pre-compute distances between all district centers to populate cache
        Only makes API calls for unique district pairs
        """
        logger.info(f"Pre-computing distances for {len(district_centers)} districts")

        district_names = list(district_centers.keys())

        # Pre-compute district-to-district distances
        for i, district1 in enumerate(district_names):
            for j, district2 in enumerate(district_names[i+1:], i+1):
                coord1 = district_centers[district1]
                coord2 = district_centers[district2]

                # Check if already cached
                if not self.cache.get_cached_district_distance(coord1, coord2):
                    logger.debug(f"Pre-computing distance: {district1} -> {district2}")
                    travel_info = self.get_travel_time(coord1, coord2, skip_api=False)
                    self.cache.cache_district_distance(coord1, coord2, travel_info)

        # Pre-compute home distances
        if home_location:
            for district_name, coord in district_centers.items():
                if not self.cache.get_cached_home_distance(coord):
                    logger.debug(f"Pre-computing home distance: {district_name} -> home")
                    travel_info = self.get_travel_time(coord, home_location, skip_api=False)
                    self.cache.cache_home_distance(coord, travel_info)

        logger.info(f"Pre-computation complete. Cache has {len(self.cache.district_to_district_cache)} district pairs and {len(self.cache.district_to_home_cache)} home distances")

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