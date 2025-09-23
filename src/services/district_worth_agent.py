"""
District Worth Agent - Calculates which districts are worth visiting based on station density and count
"""

import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from haversine import haversine, Unit

logger = logging.getLogger(__name__)

class DistrictWorthAgent:
    """Agent that calculates the worth/value of visiting different districts"""

    def __init__(self):
        self.min_stations_threshold = 2  # Minimum stations to be worth visiting
        self.max_distance_threshold = 50  # Max km radius for district compactness

    def calculate_district_worth(self,
                               district_name: str,
                               stations: List[Dict]) -> Dict[str, any]:
        """
        Calculate worth score for a district based on station count and density

        Args:
            district_name: Name of the district
            stations: List of stations in this district

        Returns:
            Dict with worth score and analysis
        """
        if not stations or len(stations) < 1:
            return {
                "district": district_name,
                "worth_score": 0,
                "station_count": 0,
                "reason": "No stations",
                "should_visit": False
            }

        station_count = len(stations)

        # Get valid coordinates
        valid_coords = []
        for station in stations:
            lat = station.get('latitude') or station.get('lat')
            lon = station.get('longitude') or station.get('long') or station.get('lon')
            if lat and lon and lat != 0 and lon != 0:
                valid_coords.append((float(lat), float(lon)))

        if len(valid_coords) < 2:
            density_score = 50  # Default for single station
            compactness_score = 50
        else:
            # Calculate density score based on area coverage
            density_score = self._calculate_density_score(valid_coords)
            compactness_score = self._calculate_compactness_score(valid_coords)

        # Base score from station count (0-40 points)
        count_score = min(40, station_count * 4)  # 4 points per station, max 40

        # Worth score calculation (0-100)
        worth_score = count_score + density_score + compactness_score

        # Determine if worth visiting
        should_visit = (
            station_count >= self.min_stations_threshold and
            worth_score >= 40
        )

        # Generate reason
        if station_count < self.min_stations_threshold:
            reason = f"Too few stations ({station_count})"
        elif worth_score < 40:
            reason = f"Low worth score ({worth_score:.1f})"
        else:
            reason = f"Good target: {station_count} stations, score {worth_score:.1f}"

        return {
            "district": district_name,
            "worth_score": round(worth_score, 1),
            "station_count": station_count,
            "density_score": round(density_score, 1),
            "compactness_score": round(compactness_score, 1),
            "should_visit": should_visit,
            "reason": reason,
            "coordinates": valid_coords
        }

    def _calculate_density_score(self, coordinates: List[Tuple[float, float]]) -> float:
        """Calculate density score based on stations per area (0-30 points)"""
        if len(coordinates) < 2:
            return 15  # Default score for single station

        # Find bounding box
        lats = [coord[0] for coord in coordinates]
        lons = [coord[1] for coord in coordinates]

        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)

        # Approximate area in km² (rough estimation)
        area_km2 = lat_range * lon_range * 111 * 111  # 1 degree ≈ 111 km
        area_km2 = max(area_km2, 1)  # Minimum 1 km²

        stations_per_km2 = len(coordinates) / area_km2

        # Score: higher density = better score (0-30)
        if stations_per_km2 > 10:
            return 30
        elif stations_per_km2 > 5:
            return 25
        elif stations_per_km2 > 1:
            return 20
        elif stations_per_km2 > 0.5:
            return 15
        else:
            return 10

    def _calculate_compactness_score(self, coordinates: List[Tuple[float, float]]) -> float:
        """Calculate compactness score - how close stations are to each other (0-30 points)"""
        if len(coordinates) < 2:
            return 15  # Default score for single station

        # Calculate average distance between all pairs
        total_distance = 0
        pair_count = 0

        for i in range(len(coordinates)):
            for j in range(i + 1, len(coordinates)):
                distance = haversine(coordinates[i], coordinates[j], unit=Unit.KILOMETERS)
                total_distance += distance
                pair_count += 1

        if pair_count == 0:
            return 15

        avg_distance = total_distance / pair_count

        # Score: closer stations = better score (0-30)
        if avg_distance < 5:
            return 30
        elif avg_distance < 10:
            return 25
        elif avg_distance < 20:
            return 20
        elif avg_distance < 30:
            return 15
        elif avg_distance < 50:
            return 10
        else:
            return 5

    def analyze_all_districts(self, stations: List[Dict]) -> List[Dict]:
        """
        Analyze all districts and return them sorted by worth

        Args:
            stations: List of all stations

        Returns:
            List of district analysis sorted by worth score (highest first)
        """
        # Group stations by district
        districts = defaultdict(list)

        for station in stations:
            district = station.get("district", "Unknown")
            districts[district].append(station)

        # Analyze each district
        district_analyses = []

        for district_name, district_stations in districts.items():
            analysis = self.calculate_district_worth(district_name, district_stations)
            district_analyses.append(analysis)

        # Sort by worth score (highest first)
        district_analyses.sort(key=lambda x: x["worth_score"], reverse=True)

        logger.info(f"Analyzed {len(district_analyses)} districts")
        for analysis in district_analyses[:5]:  # Log top 5
            logger.info(f"District '{analysis['district']}': {analysis['station_count']} stations, "
                       f"score {analysis['worth_score']}, {analysis['reason']}")

        return district_analyses

    def get_worth_districts(self, stations: List[Dict], max_districts: int = None) -> List[Dict]:
        """
        Get districts worth visiting, sorted by priority

        Args:
            stations: List of all stations
            max_districts: Maximum number of districts to return

        Returns:
            List of district analyses for districts worth visiting
        """
        all_analyses = self.analyze_all_districts(stations)

        # Filter to only worth visiting
        worth_districts = [d for d in all_analyses if d["should_visit"]]

        if max_districts:
            worth_districts = worth_districts[:max_districts]

        logger.info(f"Found {len(worth_districts)} districts worth visiting")

        return worth_districts

    def get_district_stations(self,
                            district_name: str,
                            all_stations: List[Dict]) -> List[Dict]:
        """Get all stations in a specific district"""
        return [s for s in all_stations if s.get("district") == district_name]

    def should_visit_district(self, district_name: str, stations: List[Dict]) -> bool:
        """Quick check if a district should be visited"""
        district_stations = self.get_district_stations(district_name, stations)
        analysis = self.calculate_district_worth(district_name, district_stations)
        return analysis["should_visit"]