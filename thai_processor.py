"""Thai language processing utilities"""

import re
from typing import Dict, List, Optional, Tuple
from openrouter_client import OpenRouterClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ThaiProcessor:
    """Enhanced Thai language processing for FM station planning"""

    def __init__(self):
        self.llm_client = OpenRouterClient()

        # Thai number mappings
        self.thai_numbers = {
            '๐': '0', '๑': '1', '๒': '2', '๓': '3', '๔': '4',
            '๕': '5', '๖': '6', '๗': '7', '๘': '8', '๙': '9'
        }

        # Common Thai location keywords
        self.location_keywords = {
            'provinces': [
                'กรุงเทพ', 'ชัยภูมิ', 'เชียงใหม่', 'ภูเก็ต', 'ขอนแก่น',
                'นครราชสีมา', 'อุดรธานี', 'สงขลา', 'ระยอง', 'ชลบุรี'
            ],
            'time_words': ['นาที', 'ชั่วโมง', 'ชม.', 'น.'],
            'station_words': ['สถานี', 'วิทยุ', 'FM', 'เอฟเอ็ม'],
            'route_words': ['เส้นทาง', 'ทาง', 'แผน', 'route']
        }

    def parse_thai_input(self, text: str) -> Dict:
        """
        Comprehensive Thai text parsing

        Returns:
            Dict with extracted information:
            - locations: List of location mentions
            - numbers: List of numbers found
            - time_constraints: Time requirements
            - station_count: Number of stations requested
            - special_requests: Any special requirements
        """

        # Convert Thai numbers to Arabic
        text_normalized = self.normalize_thai_numbers(text)

        # Extract all numbers
        numbers = self.extract_numbers(text_normalized)

        # Extract location mentions
        locations = self.extract_locations(text)

        # Parse time constraints
        time_constraints = self.parse_time_constraints(text_normalized, numbers)

        # Determine station count
        station_count = self.determine_station_count(text_normalized, numbers)

        # Check for route request
        needs_route = self.check_route_request(text)

        # Extract any special requirements using LLM
        special_requests = self.extract_special_requirements(text)

        result = {
            "original_text": text,
            "locations": locations,
            "numbers": numbers,
            "time_constraints": time_constraints,
            "station_count": station_count,
            "needs_route": needs_route,
            "special_requests": special_requests
        }

        logger.info(f"Parsed Thai input: {result}")
        return result

    def normalize_thai_numbers(self, text: str) -> str:
        """Convert Thai numbers to Arabic numbers"""
        result = text
        for thai_num, arabic_num in self.thai_numbers.items():
            result = result.replace(thai_num, arabic_num)
        return result

    def extract_numbers(self, text: str) -> List[int]:
        """Extract all numbers from text"""
        # Find all numeric patterns
        patterns = [
            r'\d+',  # Simple numbers
            r'\d+-\d+',  # Ranges
            r'\d+\.\d+',  # Decimals
        ]

        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if '-' in match:
                    # Handle ranges
                    parts = match.split('-')
                    numbers.extend([int(p) for p in parts if p.isdigit()])
                elif '.' in match:
                    # Handle decimals as integers
                    numbers.append(int(float(match)))
                else:
                    numbers.append(int(match))

        return numbers

    def extract_locations(self, text: str) -> List[Dict]:
        """Extract location mentions from text"""
        locations = []

        # Check for known provinces
        for province in self.location_keywords['provinces']:
            if province in text:
                locations.append({
                    "name": province,
                    "type": "province",
                    "position": text.find(province)
                })

        # Use LLM for more complex location extraction
        if not locations:
            llm_locations = self.llm_client.parse_location(text)
            if llm_locations.get("province"):
                locations.append({
                    "name": llm_locations["province"],
                    "type": "province",
                    "position": 0
                })

        # Sort by position in text
        locations.sort(key=lambda x: x["position"])

        return locations

    def parse_time_constraints(self, text: str, numbers: List[int]) -> Dict:
        """Extract time constraints from text"""
        time_info = {
            "has_constraint": False,
            "minutes": None,
            "range": None
        }

        # Look for time keywords
        time_patterns = [
            (r'(\d+)\s*-\s*(\d+)\s*(นาที|ชม\.?|ชั่วโมง)', 'range'),
            (r'ไม่เกิน\s*(\d+)\s*(นาที|ชม\.?|ชั่วโมง)', 'max'),
            (r'(\d+)\s*(นาที|ชม\.?|ชั่วโมง)', 'exact'),
            (r'ภายใน\s*(\d+)\s*(นาที|ชม\.?|ชั่วโมง)', 'within')
        ]

        for pattern, constraint_type in time_patterns:
            match = re.search(pattern, text)
            if match:
                time_info["has_constraint"] = True

                if constraint_type == 'range':
                    min_time = int(match.group(1))
                    max_time = int(match.group(2))
                    unit = match.group(3)

                    # Convert hours to minutes if needed
                    if 'ชม' in unit or 'ชั่วโมง' in unit:
                        min_time *= 60
                        max_time *= 60

                    time_info["range"] = (min_time, max_time)
                    time_info["minutes"] = max_time

                else:
                    time_value = int(match.group(1))
                    unit = match.group(2) if match.lastindex >= 2 else 'นาที'

                    # Convert hours to minutes if needed
                    if 'ชม' in unit or 'ชั่วโมง' in unit:
                        time_value *= 60

                    time_info["minutes"] = time_value

                break

        return time_info

    def determine_station_count(self, text: str, numbers: List[int]) -> int:
        """Determine how many stations are requested"""

        # Look for patterns like "10 สถานี" or "สถานี 10 แห่ง"
        station_patterns = [
            r'(\d+)\s*สถานี',
            r'สถานี\s*(\d+)\s*แห่ง',
            r'สถานี.*?(\d+)',
            r'(\d+)\s*แห่ง'
        ]

        for pattern in station_patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

        # If no explicit station count, use first reasonable number
        for num in numbers:
            if 1 <= num <= 50:  # Reasonable range for station count
                return num

        # Default to 10 stations
        return 10

    def check_route_request(self, text: str) -> bool:
        """Check if user wants route planning"""
        route_indicators = [
            'เส้นทาง', 'แผน', 'วางแผน', 'ทาง',
            'route', 'plan', 'ไปยัง', 'เดินทาง'
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in route_indicators)

    def extract_special_requirements(self, text: str) -> List[str]:
        """Extract any special requirements using LLM"""

        prompt = f"""Extract special requirements from this Thai text:
{text}

Look for:
- Specific station preferences
- Time of day preferences
- Vehicle type
- Special conditions

Return as a JSON array of requirements. If none, return empty array."""

        try:
            response = self.llm_client.complete(
                prompt,
                task_type="simple_tasks"
            )

            # Parse response
            import json
            requirements = json.loads(response)
            return requirements if isinstance(requirements, list) else []

        except Exception as e:
            logger.error(f"Failed to extract special requirements: {e}")
            return []

    def format_thai_response(self,
                           stations: List[Dict],
                           route_info: Dict,
                           requirements: Dict) -> str:
        """
        Format comprehensive Thai language response

        Creates a well-structured response with:
        - Greeting and acknowledgment
        - Station list with details
        - Route information
        - Time summary
        - Cost information
        """

        lines = []

        # Greeting based on request
        location_name = requirements.get("location", {}).get("province", "พื้นที่ที่ระบุ")
        station_count = len(stations)

        lines.append(f"✅ พบสถานี FM จำนวน {station_count} สถานีใน{location_name}")
        lines.append("")

        # Station listing
        lines.append("📍 รายการสถานี:")
        lines.append("-" * 40)

        for i, station in enumerate(stations, 1):
            # Station basic info
            name = station.get("station_name", "ไม่ระบุชื่อ")
            freq = station.get("frequency", "?")
            dist = station.get("distance_km", station.get("distance_from_start", 0))

            lines.append(f"{i}. {name} ({freq} MHz)")
            lines.append(f"   📏 ระยะทาง: {dist:.1f} กม.")

            # Add travel time if available
            if i <= len(route_info.get("segments", [])):
                segment = route_info["segments"][i-1]
                travel_time = segment.get("travel_time_minutes", 0)
                lines.append(f"   🚗 เวลาเดินทาง: {travel_time:.0f} นาที")

            lines.append(f"   🔧 เวลาตรวจสอบ: 10 นาที")
            lines.append("")

        # Route summary
        lines.append("-" * 40)
        lines.append("📊 สรุปแผนการตรวจสอบ:")
        lines.append(f"• จำนวนสถานี: {station_count} สถานี")
        lines.append(f"• ระยะทางรวม: {route_info.get('total_distance_km', 0):.1f} กม.")
        lines.append(f"• เวลาเดินทาง: {route_info.get('total_travel_time_minutes', 0):.0f} นาที")
        lines.append(f"• เวลาตรวจสอบ: {route_info.get('total_inspection_time_minutes', 0)} นาที")
        lines.append(f"• เวลารวมทั้งหมด: {route_info.get('total_time_minutes', 0):.0f} นาที")

        # Check time constraint
        if requirements.get("time_constraint_minutes"):
            max_time = requirements["time_constraint_minutes"]
            total_time = route_info.get("total_time_minutes", 0)

            if total_time <= max_time:
                lines.append(f"✅ อยู่ในเวลาที่กำหนด ({max_time} นาที)")
            else:
                lines.append(f"⚠️ เกินเวลาที่กำหนด ({max_time} นาที)")

        # Algorithm used (if optimized)
        if route_info.get("algorithm_used"):
            algo_name = route_info["algorithm_used"]
            lines.append(f"• วิธีการหาเส้นทาง: {self._translate_algorithm(algo_name)}")

        return "\n".join(lines)

    def _translate_algorithm(self, algo_name: str) -> str:
        """Translate algorithm names to Thai"""
        translations = {
            "nearest_neighbor": "เพื่อนบ้านใกล้ที่สุด",
            "2opt": "การปรับปรุงเส้นทาง 2-opt",
            "christofides": "อัลกอริทึม Christofides",
            "brute_force": "การค้นหาแบบละเอียด",
            "adaptive": "การเลือกวิธีอัตโนมัติ"
        }
        return translations.get(algo_name, algo_name)