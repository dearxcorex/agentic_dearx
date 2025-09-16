"""Supabase database connector for FM stations"""

from typing import List, Dict, Optional, Tuple
from supabase import create_client, Client
from config import Config
import logging
from haversine import haversine, Unit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StationDatabase:
    """FM Station database operations"""

    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_KEY
        )
        self.table_name = "fm_station"

    def get_stations_by_province(self, province: str, limit: int = 100) -> List[Dict]:
        """Get FM stations in a specific province (excluding inspected, not submitted, not on air)"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("province", province)\
                .neq("inspection_68", "ตรวจแล้ว")\
                .neq("submit_a_request", "ไม่ยื่น")\
                .eq("on_air", True)\
                .limit(limit)\
                .execute()

            stations = response.data
            logger.info(f"Found {len(stations)} available stations in {province}")
            return stations

        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            return []

    def get_stations_by_district(self,
                                province: str,
                                district: str,
                                limit: int = 100) -> List[Dict]:
        """Get FM stations in a specific district (excluding inspected, not submitted, not on air)"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("province", province)\
                .eq("district", district)\
                .neq("inspection_68", "ตรวจแล้ว")\
                .neq("submit_a_request", "ไม่ยื่น")\
                .eq("on_air", True)\
                .limit(limit)\
                .execute()

            stations = response.data
            logger.info(f"Found {len(stations)} available stations in {district}, {province}")
            return stations

        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            return []

    def get_all_stations(self, limit: int = 1000) -> List[Dict]:
        """Get all FM stations (up to limit, excluding inspected, not submitted, not on air)"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .neq("inspection_68", "ตรวจแล้ว")\
                .neq("submit_a_request", "ไม่ยื่น")\
                .eq("on_air", True)\
                .limit(limit)\
                .execute()

            return response.data

        except Exception as e:
            logger.error(f"Error fetching all stations: {e}")
            return []

    def get_stations_near_location(self,
                                  lat: float,
                                  lon: float,
                                  radius_km: float = 50,
                                  limit: int = 100) -> List[Dict]:
        """Get stations within radius of a location"""
        try:
            # Get all stations (we'll filter in Python since Supabase doesn't have native geospatial queries)
            all_stations = self.get_all_stations()

            nearby_stations = []
            for station in all_stations:
                if station.get("lat") and station.get("long"):
                    station_coords = (station["lat"], station["long"])
                    user_coords = (lat, lon)
                    distance = haversine(user_coords, station_coords, unit=Unit.KILOMETERS)

                    if distance <= radius_km:
                        station["distance_km"] = round(distance, 2)
                        nearby_stations.append(station)

            # Sort by distance
            nearby_stations.sort(key=lambda x: x["distance_km"])

            # Apply limit
            nearby_stations = nearby_stations[:limit]

            logger.info(f"Found {len(nearby_stations)} stations within {radius_km}km")
            return nearby_stations

        except Exception as e:
            logger.error(f"Error finding nearby stations: {e}")
            return []

    def search_stations(self,
                       search_params: Dict,
                       current_location: Optional[Tuple[float, float]] = None) -> List[Dict]:
        """Advanced station search with multiple parameters"""

        stations = []

        # Search by province
        if search_params.get("province"):
            if search_params.get("district"):
                stations = self.get_stations_by_district(
                    search_params["province"],
                    search_params["district"]
                )
            else:
                stations = self.get_stations_by_province(
                    search_params["province"]
                )

        # Search by proximity if location is provided
        elif current_location:
            # First try GPS-based proximity search
            stations = self.get_stations_near_location(
                current_location[0],
                current_location[1],
                radius_km=search_params.get("radius_km", 50)
            )

            # If no stations found with GPS (stations lack coordinates),
            # fall back to province-based search using GPS coordinates
            if not stations:
                logger.info("No stations found with GPS proximity, trying province-based fallback")
                detected_province = self._detect_province_from_gps(current_location)
                if detected_province:
                    logger.info(f"Detected province: {detected_province}")
                    stations = self.get_stations_by_province(detected_province)

                    # Try nearby provinces if still no stations
                    if not stations:
                        nearby_provinces = self._get_nearby_provinces(current_location)
                        for province in nearby_provinces[:3]:  # Try 3 closest provinces
                            province_stations = self.get_stations_by_province(province)
                            if province_stations:
                                logger.info(f"Found {len(province_stations)} stations in nearby province: {province}")
                                stations.extend(province_stations)

        # Add distance information if current location is provided
        if current_location and stations:
            for station in stations:
                if station.get("lat") and station.get("long"):
                    station_coords = (station["lat"], station["long"])
                    distance = haversine(current_location, station_coords, unit=Unit.KILOMETERS)
                    station["distance_from_start"] = round(distance, 2)
                else:
                    # For stations without GPS coordinates, estimate distance to province center
                    station["distance_from_start"] = self._estimate_distance_to_province(
                        current_location, station.get("province")
                    )

        return stations

    def _detect_province_from_gps(self, coordinates: Tuple[float, float]) -> Optional[str]:
        """Detect Thai province from GPS coordinates"""
        try:
            from location_province_mapper import ThaiProvinceMapper
            mapper = ThaiProvinceMapper()
            return mapper.get_province_from_coordinates(coordinates[0], coordinates[1])
        except ImportError:
            logger.warning("Province mapper not available")
            return None

    def _get_nearby_provinces(self, coordinates: Tuple[float, float]) -> List[str]:
        """Get nearby provinces from GPS coordinates"""
        try:
            from location_province_mapper import ThaiProvinceMapper
            mapper = ThaiProvinceMapper()
            return mapper.get_nearby_provinces(coordinates[0], coordinates[1], max_distance=1.5)
        except ImportError:
            logger.warning("Province mapper not available")
            return []

    def _estimate_distance_to_province(self, coordinates: Tuple[float, float], province: str) -> float:
        """Estimate distance from coordinates to province center"""
        try:
            from location_province_mapper import ThaiProvinceMapper
            mapper = ThaiProvinceMapper()
            if province in mapper.province_boundaries:
                province_info = mapper.province_boundaries[province]
                province_coords = (province_info["lat"], province_info["lon"])
                distance = haversine(coordinates, province_coords, unit=Unit.KILOMETERS)
                return round(distance, 2)
        except ImportError:
            pass
        return 0.0  # Default if can't calculate

    def get_uninspected_stations(self,
                               province: Optional[str] = None,
                               district: Optional[str] = None,
                               limit: int = 100) -> List[Dict]:
        """Get stations that haven't been inspected yet (inspection_68 == 'ยังไม่ตรวจ')"""
        try:
            query = self.client.table(self.table_name).select("*")

            # Filter by inspection status
            query = query.eq("inspection_68", "ยังไม่ตรวจ")

            # Add location filters if provided
            if province:
                query = query.eq("province", province)
            if district:
                query = query.eq("district", district)

            query = query.limit(limit)
            response = query.execute()

            stations = response.data
            logger.info(f"Found {len(stations)} uninspected stations")
            return stations

        except Exception as e:
            logger.error(f"Error fetching uninspected stations: {e}")
            return []

    def get_stations_by_inspection_status(self,
                                        inspection_status: str,
                                        province: Optional[str] = None,
                                        district: Optional[str] = None,
                                        limit: int = 100) -> List[Dict]:
        """Get stations by their inspection_68 status"""
        try:
            query = self.client.table(self.table_name).select("*")
            query = query.eq("inspection_68", inspection_status)

            if province:
                query = query.eq("province", province)
            if district:
                query = query.eq("district", district)

            query = query.limit(limit)
            response = query.execute()

            stations = response.data
            logger.info(f"Found {len(stations)} stations with status '{inspection_status}'")
            return stations

        except Exception as e:
            logger.error(f"Error fetching stations by inspection status: {e}")
            return []

    def enrich_stations_with_distance(self,
                                     stations: List[Dict],
                                     reference_point: Tuple[float, float]) -> List[Dict]:
        """Add distance information to stations"""
        for station in stations:
            if station.get("lat") and station.get("long"):
                station_coords = (station["lat"], station["long"])
                distance = haversine(reference_point, station_coords, unit=Unit.KILOMETERS)
                station["distance_km"] = round(distance, 2)

        # Sort by distance
        stations.sort(key=lambda x: x.get("distance_km", float('inf')))
        return stations

    def get_nearest_station(self,
                          current_location: Tuple[float, float],
                          exclude_station_ids: List[str] = None) -> Optional[Dict]:
        """Get the nearest unvisited station from current location"""
        if exclude_station_ids is None:
            exclude_station_ids = []

        try:
            # Detect province from current location
            detected_province = self._detect_province_from_gps(current_location)
            if not detected_province:
                logger.warning("Could not detect province from GPS coordinates")
                return None

            # Get all available stations in the province
            stations = self.get_stations_by_province(detected_province, limit=1000)

            if not stations:
                logger.info(f"No available stations found in {detected_province}")
                return None

            # Filter out excluded stations
            if exclude_station_ids:
                stations = [s for s in stations if str(s.get('id_fm')) not in exclude_station_ids]

            if not stations:
                logger.info("All stations in province have been visited")
                return None

            # Add distance information and find nearest
            stations_with_distance = self.enrich_stations_with_distance(stations, current_location)

            nearest_station = stations_with_distance[0]
            logger.info(f"Found nearest station: {nearest_station.get('name')} at {nearest_station.get('distance_km')}km")

            return nearest_station

        except Exception as e:
            logger.error(f"Error finding nearest station: {e}")
            return None