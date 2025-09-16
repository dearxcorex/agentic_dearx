#!/usr/bin/env python
"""
Plan Evaluation Agent for FM Station Inspection Routes
Analyzes if the generated plan is optimal and suggests improvements
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from haversine import haversine, Unit
from openrouter_client import OpenRouterClient
from config import Config

logger = logging.getLogger(__name__)

class PlanEvaluationAgent:
    """Agent to evaluate and optimize inspection plans"""

    def __init__(self):
        self.llm_client = OpenRouterClient()

    def evaluate_plan(self,
                     stations: List[Dict],
                     start_location: Tuple[float, float],
                     route_info: Dict) -> Dict[str, Any]:
        """
        Evaluate if the inspection plan is optimal

        Args:
            stations: List of stations in planned order
            start_location: Starting coordinates (lat, lon)
            route_info: Current route information

        Returns:
            Evaluation results with suggestions
        """

        if not stations:
            return {"is_optimal": True, "suggestions": [], "score": 0}

        try:
            # Analyze route efficiency
            efficiency_analysis = self._analyze_route_efficiency(stations, start_location)

            # Check for better sequencing
            optimization_suggestions = self._suggest_sequence_improvements(stations, start_location)

            # Evaluate travel patterns
            travel_analysis = self._analyze_travel_patterns(stations, start_location)

            # Generate AI-powered evaluation
            ai_evaluation = self._get_ai_evaluation(stations, efficiency_analysis, travel_analysis)

            # Calculate overall score
            overall_score = self._calculate_plan_score(efficiency_analysis, travel_analysis)

            evaluation_result = {
                "is_optimal": overall_score >= 80,  # 80+ is considered optimal
                "score": overall_score,
                "efficiency_analysis": efficiency_analysis,
                "travel_analysis": travel_analysis,
                "optimization_suggestions": optimization_suggestions,
                "ai_evaluation": ai_evaluation,
                "recommended_action": self._get_recommended_action(overall_score)
            }

            logger.info(f"Plan evaluation completed. Score: {overall_score}/100")
            return evaluation_result

        except Exception as e:
            logger.error(f"Plan evaluation error: {e}")
            return {
                "is_optimal": True,  # Default to accepting plan if evaluation fails
                "suggestions": [],
                "score": 50,
                "error": str(e)
            }

    def _analyze_route_efficiency(self, stations: List[Dict], start_location: Tuple[float, float]) -> Dict:
        """Analyze the efficiency of the route sequence"""

        if len(stations) < 2:
            return {"total_distance": 0, "efficiency_rating": "N/A", "backtracking_detected": False}

        # Calculate total distance for current route
        current_distance = self._calculate_total_distance(stations, start_location)

        # Calculate optimal distance (minimum spanning tree approximation)
        optimal_distance = self._estimate_optimal_distance(stations, start_location)

        # Detect backtracking
        backtracking_detected = self._detect_backtracking(stations, start_location)

        # Calculate efficiency ratio
        efficiency_ratio = (optimal_distance / current_distance) * 100 if current_distance > 0 else 100

        return {
            "current_distance_km": round(current_distance, 2),
            "estimated_optimal_distance_km": round(optimal_distance, 2),
            "efficiency_percentage": round(efficiency_ratio, 1),
            "backtracking_detected": backtracking_detected,
            "efficiency_rating": self._get_efficiency_rating(efficiency_ratio)
        }

    def _suggest_sequence_improvements(self, stations: List[Dict], start_location: Tuple[float, float]) -> List[str]:
        """Suggest improvements to station sequence"""

        suggestions = []

        if len(stations) < 2:
            return suggestions

        # Check for obvious improvements
        inefficient_jumps = self._find_inefficient_jumps(stations, start_location)

        if inefficient_jumps:
            suggestions.extend([
                f"Consider reordering stations {inefficient_jumps['station_a']} and {inefficient_jumps['station_b']} to reduce travel distance",
                f"Current jump distance: {inefficient_jumps['distance']:.1f} km - could be optimized"
            ])

        # Check for clustering opportunities
        clusters = self._identify_station_clusters(stations)
        if len(clusters) > 1:
            suggestions.append("Consider visiting stations in geographical clusters to minimize travel time")

        # Check starting point optimization
        better_start = self._find_better_starting_station(stations, start_location)
        if better_start:
            suggestions.append(f"Consider starting with station '{better_start['name']}' to optimize overall route")

        return suggestions

    def _analyze_travel_patterns(self, stations: List[Dict], start_location: Tuple[float, float]) -> Dict:
        """Analyze travel patterns between stations"""

        if len(stations) < 2:
            return {"average_jump_distance": 0, "max_jump_distance": 0, "pattern": "single_station"}

        jump_distances = []
        current_pos = start_location

        for station in stations:
            if station.get("latitude") and station.get("longitude"):
                station_pos = (station["latitude"], station["longitude"])
                distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                jump_distances.append(distance)
                current_pos = station_pos
            else:
                # Estimate distance if no coordinates
                jump_distances.append(25.0)  # Default estimate

        if not jump_distances:
            return {"average_jump_distance": 0, "max_jump_distance": 0, "pattern": "unknown"}

        avg_jump = sum(jump_distances) / len(jump_distances)
        max_jump = max(jump_distances)
        min_jump = min(jump_distances)

        # Analyze pattern
        pattern = self._classify_travel_pattern(jump_distances)

        return {
            "average_jump_distance_km": round(avg_jump, 2),
            "max_jump_distance_km": round(max_jump, 2),
            "min_jump_distance_km": round(min_jump, 2),
            "jump_distances": [round(d, 2) for d in jump_distances],
            "pattern": pattern,
            "consistency_score": self._calculate_consistency_score(jump_distances)
        }

    def _get_ai_evaluation(self, stations: List[Dict], efficiency_analysis: Dict, travel_analysis: Dict) -> str:
        """Get AI-powered evaluation of the plan"""

        try:
            model_config = Config.get_model("complex_reasoning")

            prompt = f"""Analyze this FM station inspection route and provide expert feedback:

ROUTE ANALYSIS:
- Number of stations: {len(stations)}
- Current route distance: {efficiency_analysis.get('current_distance_km', 0)} km
- Efficiency: {efficiency_analysis.get('efficiency_percentage', 0)}%
- Average jump between stations: {travel_analysis.get('average_jump_distance_km', 0)} km
- Max jump distance: {travel_analysis.get('max_jump_distance_km', 0)} km
- Travel pattern: {travel_analysis.get('pattern', 'unknown')}
- Backtracking detected: {efficiency_analysis.get('backtracking_detected', False)}

STATIONS IN ORDER:
{self._format_stations_for_ai(stations)}

Provide a brief evaluation (2-3 sentences) focusing on:
1. Is this route sequence logical for field inspections?
2. Are there obvious inefficiencies in station-to-station movement?
3. One specific recommendation to improve the route.

Keep response concise and practical for field work."""

            messages = [{"role": "user", "content": prompt}]

            response = self.llm_client._make_request(messages, model_config)

            if response and "choices" in response:
                evaluation = response["choices"][0]["message"]["content"].strip()
                return evaluation
            else:
                return "Route appears acceptable for field inspection work."

        except Exception as e:
            logger.error(f"AI evaluation failed: {e}")
            return "Route evaluation completed - basic analysis available."

    def _calculate_total_distance(self, stations: List[Dict], start_location: Tuple[float, float]) -> float:
        """Calculate total distance for current route"""

        if not stations:
            return 0.0

        total_distance = 0.0
        current_pos = start_location

        for station in stations:
            if station.get("latitude") and station.get("longitude"):
                station_pos = (station["latitude"], station["longitude"])
                distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                total_distance += distance
                current_pos = station_pos
            else:
                # Use province-based estimate
                total_distance += station.get("distance_from_start", 25.0)

        return total_distance

    def _estimate_optimal_distance(self, stations: List[Dict], start_location: Tuple[float, float]) -> float:
        """Estimate optimal distance using nearest neighbor heuristic"""

        if len(stations) < 2:
            return self._calculate_total_distance(stations, start_location)

        # Simple nearest neighbor estimation
        unvisited = stations.copy()
        current_pos = start_location
        total_distance = 0.0

        while unvisited:
            nearest_station = None
            min_distance = float('inf')

            for station in unvisited:
                if station.get("latitude") and station.get("longitude"):
                    station_pos = (station["latitude"], station["longitude"])
                    distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                else:
                    distance = station.get("distance_from_start", 25.0)

                if distance < min_distance:
                    min_distance = distance
                    nearest_station = station

            if nearest_station:
                total_distance += min_distance
                unvisited.remove(nearest_station)

                if nearest_station.get("latitude") and nearest_station.get("longitude"):
                    current_pos = (nearest_station["latitude"], nearest_station["longitude"])

        return total_distance

    def _detect_backtracking(self, stations: List[Dict], start_location: Tuple[float, float]) -> bool:
        """Detect if route involves significant backtracking"""

        if len(stations) < 3:
            return False

        # Check for direction changes that indicate backtracking
        positions = [start_location]

        for station in stations:
            if station.get("latitude") and station.get("longitude"):
                positions.append((station["latitude"], station["longitude"]))

        if len(positions) < 3:
            return False

        # Simple backtracking detection based on direction changes
        direction_changes = 0
        for i in range(len(positions) - 2):
            # Calculate vectors
            v1 = (positions[i+1][0] - positions[i][0], positions[i+1][1] - positions[i][1])
            v2 = (positions[i+2][0] - positions[i+1][0], positions[i+2][1] - positions[i+1][1])

            # Calculate dot product to detect direction changes
            dot_product = v1[0] * v2[0] + v1[1] * v2[1]

            if dot_product < 0:  # Vectors pointing in opposite directions
                direction_changes += 1

        # If more than 40% of moves involve backtracking
        return direction_changes > len(positions) * 0.4

    def _get_efficiency_rating(self, efficiency_ratio: float) -> str:
        """Get textual efficiency rating"""
        if efficiency_ratio >= 90:
            return "Excellent"
        elif efficiency_ratio >= 80:
            return "Good"
        elif efficiency_ratio >= 70:
            return "Fair"
        elif efficiency_ratio >= 60:
            return "Poor"
        else:
            return "Very Poor"

    def _find_inefficient_jumps(self, stations: List[Dict], start_location: Tuple[float, float]) -> Optional[Dict]:
        """Find inefficient jumps between stations"""

        if len(stations) < 2:
            return None

        max_inefficient_jump = {"distance": 0, "station_a": None, "station_b": None}

        current_pos = start_location
        for i, station in enumerate(stations):
            if station.get("latitude") and station.get("longitude"):
                station_pos = (station["latitude"], station["longitude"])
                distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)

                # Consider a jump inefficient if it's much longer than average
                if distance > 50:  # Arbitrary threshold for now
                    if distance > max_inefficient_jump["distance"]:
                        max_inefficient_jump.update({
                            "distance": distance,
                            "station_a": i,
                            "station_b": i + 1,
                            "from_pos": current_pos,
                            "to_pos": station_pos
                        })

                current_pos = station_pos

        return max_inefficient_jump if max_inefficient_jump["distance"] > 0 else None

    def _identify_station_clusters(self, stations: List[Dict]) -> List[List[Dict]]:
        """Identify geographical clusters of stations"""
        # Simple clustering - group stations within 20km of each other
        clusters = []
        processed = set()

        for i, station in enumerate(stations):
            if i in processed or not (station.get("latitude") and station.get("longitude")):
                continue

            cluster = [station]
            processed.add(i)
            station_pos = (station["latitude"], station["longitude"])

            for j, other_station in enumerate(stations[i+1:], i+1):
                if j in processed or not (other_station.get("latitude") and other_station.get("longitude")):
                    continue

                other_pos = (other_station["latitude"], other_station["longitude"])
                distance = haversine(station_pos, other_pos, unit=Unit.KILOMETERS)

                if distance <= 20:  # 20km clustering threshold
                    cluster.append(other_station)
                    processed.add(j)

            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

    def _find_better_starting_station(self, stations: List[Dict], start_location: Tuple[float, float]) -> Optional[Dict]:
        """Find if there's a better starting station"""

        if not stations:
            return None

        # Find the station closest to start location
        closest_station = None
        min_distance = float('inf')

        for station in stations:
            if station.get("latitude") and station.get("longitude"):
                station_pos = (station["latitude"], station["longitude"])
                distance = haversine(start_location, station_pos, unit=Unit.KILOMETERS)

                if distance < min_distance:
                    min_distance = distance
                    closest_station = station

        # If the closest station is not the first one, suggest it
        if closest_station and closest_station != stations[0] and min_distance < 10:
            return {"name": closest_station.get("station_name", "Unknown"), "distance": min_distance}

        return None

    def _classify_travel_pattern(self, jump_distances: List[float]) -> str:
        """Classify the travel pattern"""
        if not jump_distances:
            return "unknown"

        avg_distance = sum(jump_distances) / len(jump_distances)
        max_distance = max(jump_distances)
        min_distance = min(jump_distances)

        if max_distance - min_distance < 10:
            return "consistent"
        elif max_distance > avg_distance * 2:
            return "mixed_with_long_jumps"
        elif all(d < 20 for d in jump_distances):
            return "clustered"
        else:
            return "scattered"

    def _calculate_consistency_score(self, jump_distances: List[float]) -> float:
        """Calculate how consistent the jump distances are (0-100)"""
        if not jump_distances:
            return 100

        avg_distance = sum(jump_distances) / len(jump_distances)
        variance = sum((d - avg_distance) ** 2 for d in jump_distances) / len(jump_distances)
        std_dev = variance ** 0.5

        # Convert to consistency score (lower variance = higher consistency)
        consistency = max(0, 100 - (std_dev / avg_distance * 100)) if avg_distance > 0 else 100
        return round(consistency, 1)

    def _calculate_plan_score(self, efficiency_analysis: Dict, travel_analysis: Dict) -> float:
        """Calculate overall plan score (0-100)"""

        score = 0

        # Efficiency score (40% weight)
        efficiency_pct = efficiency_analysis.get("efficiency_percentage", 50)
        score += efficiency_pct * 0.4

        # Consistency score (30% weight)
        consistency = travel_analysis.get("consistency_score", 50)
        score += consistency * 0.3

        # Pattern score (20% weight)
        pattern = travel_analysis.get("pattern", "unknown")
        pattern_scores = {
            "consistent": 90,
            "clustered": 85,
            "scattered": 60,
            "mixed_with_long_jumps": 40,
            "unknown": 50
        }
        score += pattern_scores.get(pattern, 50) * 0.2

        # Backtracking penalty (10% weight)
        if efficiency_analysis.get("backtracking_detected", False):
            score += 30 * 0.1  # Penalty for backtracking
        else:
            score += 90 * 0.1

        return round(min(100, max(0, score)), 1)

    def _get_recommended_action(self, score: float) -> str:
        """Get recommended action based on score"""
        if score >= 85:
            return "Accept plan - excellent route optimization"
        elif score >= 75:
            return "Accept plan - good route with minor optimization opportunities"
        elif score >= 60:
            return "Consider optimization - route has room for improvement"
        else:
            return "Optimize route - significant improvements possible"

    def _format_stations_for_ai(self, stations: List[Dict]) -> str:
        """Format station list for AI evaluation"""
        formatted = []
        for i, station in enumerate(stations, 1):
            name = station.get("station_name", "Unknown")
            distance = station.get("distance_from_start", 0)
            formatted.append(f"{i}. {name} ({distance} km from start)")

        return "\n".join(formatted)

def test_plan_evaluator():
    """Test the plan evaluator"""
    print("=== Testing Plan Evaluation Agent ===")

    # Sample stations for testing
    sample_stations = [
        {"station_name": "Station A", "latitude": 14.9, "longitude": 102.0, "distance_from_start": 5},
        {"station_name": "Station B", "latitude": 15.0, "longitude": 102.1, "distance_from_start": 15},
        {"station_name": "Station C", "latitude": 14.95, "longitude": 102.05, "distance_from_start": 10},
    ]

    start_location = (14.938737, 102.060821)

    evaluator = PlanEvaluationAgent()
    evaluation = evaluator.evaluate_plan(sample_stations, start_location, {})

    print(f"Plan Score: {evaluation.get('score', 0)}/100")
    print(f"Is Optimal: {evaluation.get('is_optimal', False)}")
    print(f"Recommended Action: {evaluation.get('recommended_action', 'N/A')}")

    if evaluation.get("optimization_suggestions"):
        print("\nSuggestions:")
        for suggestion in evaluation["optimization_suggestions"]:
            print(f"- {suggestion}")

if __name__ == "__main__":
    test_plan_evaluator()