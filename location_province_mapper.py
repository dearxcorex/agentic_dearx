#!/usr/bin/env python
"""
Province mapper for GPS coordinates in Thailand
Maps GPS coordinates to Thai provinces for fallback when stations lack coordinates
"""

from typing import Tuple, Optional

class ThaiProvinceMapper:
    """Maps GPS coordinates to Thai provinces"""

    def __init__(self):
        # Thailand province boundaries (approximate center points and regions)
        self.province_boundaries = {
            # Northern Thailand
            "เชียงใหม่": {"lat": 18.7883, "lon": 98.9853, "bounds": {"n": 20.5, "s": 17.5, "e": 100.0, "w": 97.5}},
            "เชียงราย": {"lat": 19.9071, "lon": 99.8325, "bounds": {"n": 20.5, "s": 19.0, "e": 100.5, "w": 99.0}},

            # Northeastern Thailand (Isan)
            "ชัยภูมิ": {"lat": 15.8069, "lon": 102.0313, "bounds": {"n": 16.5, "s": 15.0, "e": 102.8, "w": 101.2}},
            "ขอนแก่น": {"lat": 16.4322, "lon": 102.8236, "bounds": {"n": 17.0, "s": 15.5, "e": 103.5, "w": 102.0}},
            "นครราชสีมา": {"lat": 14.9799, "lon": 102.0977, "bounds": {"n": 15.7, "s": 14.2, "e": 102.8, "w": 101.3}},
            "อุดรธานี": {"lat": 17.4138, "lon": 102.7870, "bounds": {"n": 18.0, "s": 16.8, "e": 103.5, "w": 102.0}},
            "สุรินทร์": {"lat": 14.8818, "lon": 103.4931, "bounds": {"n": 15.5, "s": 14.2, "e": 104.5, "w": 102.8}},
            "บุรีรัมย์": {"lat": 14.9930, "lon": 103.1029, "bounds": {"n": 15.7, "s": 14.2, "e": 103.8, "w": 102.3}},
            "ศีสเกษ": {"lat": 15.1186, "lon": 104.3227, "bounds": {"n": 15.8, "s": 14.4, "e": 105.0, "w": 103.5}},
            "มหาสารคาม": {"lat": 16.1850, "lon": 103.3000, "bounds": {"n": 16.7, "s": 15.6, "e": 104.0, "w": 102.6}},
            "ร้อยเอ็ด": {"lat": 16.0544, "lon": 103.6531, "bounds": {"n": 16.8, "s": 15.3, "e": 104.5, "w": 103.0}},

            # Central Thailand
            "กรุงเทพมหานคร": {"lat": 13.7563, "lon": 100.5018, "bounds": {"n": 13.95, "s": 13.5, "e": 100.9, "w": 100.1}},
            "นนทบุรี": {"lat": 13.8621, "lon": 100.5144, "bounds": {"n": 14.0, "s": 13.7, "e": 100.7, "w": 100.3}},
            "ปทุมธานี": {"lat": 14.0208, "lon": 100.5250, "bounds": {"n": 14.3, "s": 13.8, "e": 100.8, "w": 100.2}},
            "สมุทรปราการ": {"lat": 13.5991, "lon": 100.5998, "bounds": {"n": 13.9, "s": 13.3, "e": 101.0, "w": 100.2}},
            "นครปฐม": {"lat": 13.8199, "lon": 100.0407, "bounds": {"n": 14.2, "s": 13.4, "e": 100.5, "w": 99.5}},

            # Eastern Thailand
            "ชลบุรี": {"lat": 13.3611, "lon": 100.9847, "bounds": {"n": 13.9, "s": 12.8, "e": 101.7, "w": 100.4}},
            "ระยอง": {"lat": 12.6802, "lon": 101.2805, "bounds": {"n": 13.2, "s": 12.1, "e": 101.8, "w": 100.8}},
            "จันทบุรี": {"lat": 12.6103, "lon": 102.1040, "bounds": {"n": 13.2, "s": 12.0, "e": 102.7, "w": 101.5}},

            # Southern Thailand
            "ภูเก็ต": {"lat": 7.8804, "lon": 98.3923, "bounds": {"n": 8.3, "s": 7.6, "e": 98.5, "w": 98.2}},
            "สงขลา": {"lat": 7.0061, "lon": 100.4959, "bounds": {"n": 7.8, "s": 6.2, "e": 101.0, "w": 100.0}},
            "สุราษฎร์ธานี": {"lat": 9.1382, "lon": 99.3215, "bounds": {"n": 9.8, "s": 8.4, "e": 100.0, "w": 98.6}},

            # Western Thailand
            "กาญจนบุรี": {"lat": 14.0227, "lon": 99.5328, "bounds": {"n": 15.0, "s": 13.4, "e": 99.9, "w": 98.9}},
            "เพชรบุรี": {"lat": 13.1110, "lon": 99.9391, "bounds": {"n": 13.6, "s": 12.6, "e": 100.2, "w": 99.7}}
        }

    def get_province_from_coordinates(self, lat: float, lon: float) -> Optional[str]:
        """Get Thai province name from GPS coordinates"""

        # Check each province boundary
        for province, info in self.province_boundaries.items():
            bounds = info["bounds"]
            if (bounds["s"] <= lat <= bounds["n"] and
                bounds["w"] <= lon <= bounds["e"]):
                return province

        # If no exact match, find closest province center
        min_distance = float('inf')
        closest_province = None

        for province, info in self.province_boundaries.items():
            distance = ((lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_province = province

        return closest_province

    def get_nearby_provinces(self, lat: float, lon: float, max_distance: float = 1.0) -> list:
        """Get list of nearby provinces within max_distance degrees"""
        nearby = []

        for province, info in self.province_boundaries.items():
            distance = ((lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2) ** 0.5
            if distance <= max_distance:
                nearby.append((province, distance))

        # Sort by distance
        nearby.sort(key=lambda x: x[1])
        return [province for province, _ in nearby]

def test_province_mapper():
    """Test the province mapper"""
    mapper = ThaiProvinceMapper()

    # Test coordinates
    test_coords = [
        (14.938737322657747, 102.06082160579989, "Your location"),
        (13.7563, 100.5018, "Bangkok"),
        (18.7883, 98.9853, "Chiang Mai"),
        (15.8069, 102.0313, "Chaiyaphum center")
    ]

    print("=== Province Mapping Test ===")
    for lat, lon, description in test_coords:
        province = mapper.get_province_from_coordinates(lat, lon)
        nearby = mapper.get_nearby_provinces(lat, lon, max_distance=0.5)
        print(f"{description} ({lat}, {lon})")
        print(f"  Province: {province}")
        print(f"  Nearby: {nearby[:3]}")
        print()

if __name__ == "__main__":
    test_province_mapper()