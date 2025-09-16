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
        """Get FM stations in a specific province"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("province", province)\
                .limit(limit)\
                .execute()

            stations = response.data
            logger.info(f"Found {len(stations)} stations in {province}")
            return stations

        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            return []

    def get_stations_by_district(self,
                                province: str,
                                district: str,
                                limit: int = 100) -> List[Dict]:
        """Get FM stations in a specific district"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("province", province)\
                .eq("district", district)\
                .limit(limit)\
                .execute()

            stations = response.data
            logger.info(f"Found {len(stations)} stations in {district}, {province}")
            return stations

        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            return []

    def get_all_stations(self, limit: int = 1000) -> List[Dict]:
        """Get all FM stations (up to limit)"""
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
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
                if station.get("latitude") and station.get("longitude"):
                    station_coords = (station["latitude"], station["longitude"])
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
            stations = self.get_stations_near_location(
                current_location[0],
                current_location[1],
                radius_km=search_params.get("radius_km", 50)
            )

        # Add distance information if current location is provided
        if current_location and stations:
            for station in stations:
                if station.get("latitude") and station.get("longitude"):
                    station_coords = (station["latitude"], station["longitude"])
                    distance = haversine(current_location, station_coords, unit=Unit.KILOMETERS)
                    station["distance_from_start"] = round(distance, 2)

        return stations

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
            if station.get("latitude") and station.get("longitude"):
                station_coords = (station["latitude"], station["longitude"])
                distance = haversine(reference_point, station_coords, unit=Unit.KILOMETERS)
                station["distance_km"] = round(distance, 2)

        # Sort by distance
        stations.sort(key=lambda x: x.get("distance_km", float('inf')))
        return stations