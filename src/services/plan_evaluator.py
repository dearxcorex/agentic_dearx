#!/usr/bin/env python
"""
Plan Evaluation Agent for FM Station Inspection Routes
Analyzes if the generated plan is optimal and suggests improvements
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from haversine import haversine, Unit
from .openrouter_client import OpenRouterClient
from ..config.config import Config

logger = logging.getLogger(__name__)

class PlanEvaluationAgent:
    """Agent to evaluate and optimize inspection plans"""

    def __init__(self):
        self.llm_client = OpenRouterClient()

    def evaluate_plan(self,
                     stations: List[Dict],
                     start_location: Tuple[float, float],
                     route_info: Dict,
                     daily_plans: Optional[List[Dict]] = None,
                     requested_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Evaluate if the inspection plan is optimal and safe for the user

        Args:
            stations: List of stations in planned order
            start_location: Starting coordinates (lat, lon)
            route_info: Current route information
            daily_plans: List of daily plans with distances and times
            requested_days: Number of days requested by user

        Returns:
            Evaluation results with suggestions including fatigue analysis
        """

        if not stations:
            return {"is_optimal": True, "suggestions": [], "score": 0}

        try:
            # Debug: Check station coordinates
            stations_with_coords = 0
            stations_with_distances = 0

            for station in stations:
                lat = station.get("latitude") or station.get("lat")
                lon = station.get("longitude") or station.get("long") or station.get("lon")
                distance = (station.get("distance_from_start") or
                           station.get("travel_distance_km") or
                           station.get("distance"))

                if lat and lon and lat != 0 and lon != 0:
                    stations_with_coords += 1
                if distance and distance > 0:
                    stations_with_distances += 1

            logger.info(f"Plan evaluation: {len(stations)} stations, {stations_with_coords} with GPS, {stations_with_distances} with distances")
            # Analyze route efficiency
            efficiency_analysis = self._analyze_route_efficiency(stations, start_location)

            # Check for better sequencing
            optimization_suggestions = self._suggest_sequence_improvements(stations, start_location)

            # Evaluate travel patterns
            travel_analysis = self._analyze_travel_patterns(stations, start_location)

            # Analyze fatigue and difficulty
            fatigue_analysis = self._analyze_fatigue_and_difficulty(daily_plans, requested_days)

            # Check if plan needs day extension
            day_recommendation = self._check_day_extension_needed(daily_plans, requested_days)

            # Generate AI-powered evaluation
            ai_evaluation = self._get_ai_evaluation(stations, efficiency_analysis, travel_analysis, fatigue_analysis)

            # Calculate overall score
            overall_score = self._calculate_plan_score(efficiency_analysis, travel_analysis, fatigue_analysis)

            evaluation_result = {
                "is_optimal": overall_score >= 80 and not day_recommendation.get("extend_days", False),
                "score": overall_score,
                "efficiency_analysis": efficiency_analysis,
                "travel_analysis": travel_analysis,
                "fatigue_analysis": fatigue_analysis,
                "day_recommendation": day_recommendation,
                "optimization_suggestions": optimization_suggestions,
                "ai_evaluation": ai_evaluation,
                "recommended_action": self._get_recommended_action(overall_score, day_recommendation, fatigue_analysis)
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
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")

            if lat and lon and lat != 0 and lon != 0:
                station_pos = (float(lat), float(lon))
                distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                jump_distances.append(distance)
                current_pos = station_pos
            else:
                # Use distance_from_start if available, otherwise estimate
                distance = station.get("distance_from_start") or station.get("travel_distance_km") or 25.0
                jump_distances.append(float(distance))

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

    def _get_ai_evaluation(self, stations: List[Dict], efficiency_analysis: Dict, travel_analysis: Dict, fatigue_analysis: Optional[Dict] = None) -> str:
        """Get AI-powered evaluation of the plan"""

        try:
            model_config = Config.get_model("complex_reasoning")

            fatigue_info = ""
            if fatigue_analysis:
                fatigue_info = f"""
FATIGUE & SAFETY ANALYSIS:
- Fatigue level: {fatigue_analysis.get('fatigue_level', 'unknown')}
- Total distance: {fatigue_analysis.get('total_distance_km', 0)} km
- Average daily distance: {fatigue_analysis.get('avg_daily_distance_km', 0)} km
- Average daily work time: {fatigue_analysis.get('avg_daily_time_hours', 0)} hours
- Is too demanding: {fatigue_analysis.get('is_too_demanding', False)}
- Fatigue factors: {', '.join(fatigue_analysis.get('fatigue_factors', []))}"""

            prompt = f"""Analyze this FM station inspection route and provide expert feedback:

ROUTE ANALYSIS:
- Number of stations: {len(stations)}
- Current route distance: {efficiency_analysis.get('current_distance_km', 0)} km
- Efficiency: {efficiency_analysis.get('efficiency_percentage', 0)}%
- Average jump between stations: {travel_analysis.get('average_jump_distance_km', 0)} km
- Max jump distance: {travel_analysis.get('max_jump_distance_km', 0)} km
- Travel pattern: {travel_analysis.get('pattern', 'unknown')}
- Backtracking detected: {efficiency_analysis.get('backtracking_detected', False)}
{fatigue_info}

STATIONS IN ORDER:
{self._format_stations_for_ai(stations)}

Provide a brief evaluation (2-3 sentences) focusing on:
1. Is this route sequence logical for field inspections?
2. Are there obvious inefficiencies in station-to-station movement?
3. Is the workload manageable or too demanding for the inspector?
4. One specific recommendation to improve safety and efficiency.

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
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")

            if lat and lon and lat != 0 and lon != 0:
                station_pos = (float(lat), float(lon))
                distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                total_distance += distance
                current_pos = station_pos
            else:
                # Use pre-calculated distance if available
                distance = station.get("distance_from_start") or station.get("travel_distance_km") or 25.0
                total_distance += float(distance)

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
                # Try different coordinate field names
                lat = station.get("latitude") or station.get("lat")
                lon = station.get("longitude") or station.get("long") or station.get("lon")

                if lat and lon and lat != 0 and lon != 0:
                    station_pos = (float(lat), float(lon))
                    distance = haversine(current_pos, station_pos, unit=Unit.KILOMETERS)
                else:
                    distance = station.get("distance_from_start") or station.get("travel_distance_km") or 25.0

                if distance < min_distance:
                    min_distance = distance
                    nearest_station = station

            if nearest_station:
                total_distance += min_distance
                unvisited.remove(nearest_station)

                # Update position if coordinates are available
                lat = nearest_station.get("latitude") or nearest_station.get("lat")
                lon = nearest_station.get("longitude") or nearest_station.get("long") or nearest_station.get("lon")
                if lat and lon and lat != 0 and lon != 0:
                    current_pos = (float(lat), float(lon))

        return total_distance

    def _detect_backtracking(self, stations: List[Dict], start_location: Tuple[float, float]) -> bool:
        """Detect if route involves significant backtracking"""

        if len(stations) < 3:
            return False

        # Check for direction changes that indicate backtracking
        positions = [start_location]

        for station in stations:
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")
            if lat and lon and lat != 0 and lon != 0:
                positions.append((float(lat), float(lon)))

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
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")

            if lat and lon and lat != 0 and lon != 0:
                station_pos = (float(lat), float(lon))
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
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")

            if i in processed or not (lat and lon and lat != 0 and lon != 0):
                continue

            cluster = [station]
            processed.add(i)
            station_pos = (float(lat), float(lon))

            for j, other_station in enumerate(stations[i+1:], i+1):
                # Try different coordinate field names for other station
                other_lat = other_station.get("latitude") or other_station.get("lat")
                other_lon = other_station.get("longitude") or other_station.get("long") or other_station.get("lon")

                if j in processed or not (other_lat and other_lon and other_lat != 0 and other_lon != 0):
                    continue

                other_pos = (float(other_lat), float(other_lon))
                distance = haversine(station_pos, other_pos, unit=Unit.KILOMETERS)

                if distance <= 20:  # 20km clustering threshold
                    cluster.append(other_station)
                    processed.add(j)

            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

    def _analyze_fatigue_and_difficulty(self, daily_plans: Optional[List[Dict]], requested_days: Optional[int]) -> Dict[str, Any]:
        """Analyze fatigue factors and difficulty level for the user"""

        if not daily_plans:
            return {"fatigue_level": "unknown", "is_too_demanding": False, "recommendations": []}

        total_distance = sum(plan.get("total_distance_km", 0) for plan in daily_plans)
        total_time = sum(plan.get("total_time_minutes", 0) for plan in daily_plans)
        total_stations = sum(len(plan.get("stations", [])) for plan in daily_plans)

        # Calculate daily averages
        num_days = len(daily_plans)
        avg_daily_distance = total_distance / num_days if num_days > 0 else 0
        avg_daily_time = total_time / num_days if num_days > 0 else 0
        avg_stations_per_day = total_stations / num_days if num_days > 0 else 0

        # Fatigue thresholds
        high_daily_distance = 300  # km per day
        high_daily_time = 480      # 8 hours per day
        high_stations_per_day = 15  # stations per day

        fatigue_factors = []
        recommendations = []

        # Check distance fatigue
        if avg_daily_distance > high_daily_distance:
            fatigue_factors.append(f"High daily driving: {avg_daily_distance:.1f} km/day")
            recommendations.append("Consider reducing daily driving distance to under 300km")

        # Check time fatigue
        if avg_daily_time > high_daily_time:
            fatigue_factors.append(f"Long work days: {avg_daily_time/60:.1f} hours/day")
            recommendations.append("Consider reducing daily work time to under 8 hours")

        # Check station workload
        if avg_stations_per_day > high_stations_per_day:
            fatigue_factors.append(f"Heavy inspection load: {avg_stations_per_day:.1f} stations/day")
            recommendations.append("Consider reducing daily inspections to under 15 stations")

        # Check for consecutive long days
        consecutive_long_days = 0
        for plan in daily_plans:
            if plan.get("total_distance_km", 0) > high_daily_distance or plan.get("total_time_minutes", 0) > high_daily_time:
                consecutive_long_days += 1

        if consecutive_long_days > 1:
            fatigue_factors.append("Multiple consecutive demanding days")
            recommendations.append("Add rest periods or extend to more days")

        # Determine fatigue level
        if len(fatigue_factors) == 0:
            fatigue_level = "low"
        elif len(fatigue_factors) <= 2:
            fatigue_level = "moderate"
        else:
            fatigue_level = "high"

        is_too_demanding = fatigue_level == "high" or avg_daily_distance > 350 or total_distance > 500

        return {
            "fatigue_level": fatigue_level,
            "is_too_demanding": is_too_demanding,
            "total_distance_km": round(total_distance, 1),
            "total_time_hours": round(total_time / 60, 1),
            "avg_daily_distance_km": round(avg_daily_distance, 1),
            "avg_daily_time_hours": round(avg_daily_time / 60, 1),
            "avg_stations_per_day": round(avg_stations_per_day, 1),
            "fatigue_factors": fatigue_factors,
            "recommendations": recommendations,
            "consecutive_long_days": consecutive_long_days
        }

    def _check_day_extension_needed(self, daily_plans: Optional[List[Dict]], requested_days: Optional[int]) -> Dict[str, Any]:
        """Check if the plan needs to be extended to more days"""

        if not daily_plans or not requested_days:
            return {"extend_days": False, "recommended_days": requested_days}

        total_distance = sum(plan.get("total_distance_km", 0) for plan in daily_plans)

        # Key thresholds for extending days (now much more lenient)
        distance_threshold_2_to_3_days = 800  # km total for 2 days (increased from 500)
        distance_threshold_per_day = 500      # km per day maximum (increased from 300)

        extend_days = False
        recommended_days = requested_days
        reasons = []

        # Check if 2-day plan exceeds lenient threshold
        if requested_days == 2 and total_distance > distance_threshold_2_to_3_days:
            extend_days = True
            recommended_days = 3
            reasons.append(f"Total distance {total_distance:.1f}km is quite extensive for 2 days")

        # Check if any single day exceeds daily limit
        for i, plan in enumerate(daily_plans, 1):
            daily_distance = plan.get("total_distance_km", 0)
            if daily_distance > distance_threshold_per_day:
                extend_days = True
                if requested_days == 2:
                    recommended_days = 3
                elif requested_days == 1:
                    recommended_days = 2
                reasons.append(f"Day {i} distance {daily_distance:.1f}km is quite extensive")

        # Check for excessive work hours
        for i, plan in enumerate(daily_plans, 1):
            daily_time = plan.get("total_time_minutes", 0)
            if daily_time > 600:  # 10 hours (increased from 8)
                extend_days = True
                if requested_days == 2:
                    recommended_days = 3
                elif requested_days == 1:
                    recommended_days = 2
                reasons.append(f"Day {i} work time {daily_time/60:.1f} hours is quite long")

        return {
            "extend_days": extend_days,
            "recommended_days": recommended_days,
            "original_days": requested_days,
            "total_distance_km": round(total_distance, 1),
            "reasons": reasons,
            "message": f"Recommend extending to {recommended_days} days for safety and comfort" if extend_days else "Current day plan is manageable"
        }

    def _find_better_starting_station(self, stations: List[Dict], start_location: Tuple[float, float]) -> Optional[Dict]:
        """Find if there's a better starting station"""

        if not stations:
            return None

        # Find the station closest to start location
        closest_station = None
        min_distance = float('inf')

        for station in stations:
            # Try different coordinate field names
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")

            if lat and lon and lat != 0 and lon != 0:
                station_pos = (float(lat), float(lon))
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

    def _calculate_plan_score(self, efficiency_analysis: Dict, travel_analysis: Dict, fatigue_analysis: Optional[Dict] = None) -> float:
        """Calculate overall plan score (0-100)"""

        score = 0

        # If fatigue analysis is available, adjust weights
        if fatigue_analysis:
            # Efficiency score (30% weight)
            efficiency_pct = efficiency_analysis.get("efficiency_percentage", 50)
            score += efficiency_pct * 0.3

            # Consistency score (20% weight)
            consistency = travel_analysis.get("consistency_score", 50)
            score += consistency * 0.2

            # Pattern score (15% weight)
            pattern = travel_analysis.get("pattern", "unknown")
            pattern_scores = {
                "consistent": 90,
                "clustered": 85,
                "scattered": 60,
                "mixed_with_long_jumps": 40,
                "unknown": 50
            }
            score += pattern_scores.get(pattern, 50) * 0.15

            # Fatigue score (25% weight) - Most important for user safety
            fatigue_level = fatigue_analysis.get("fatigue_level", "unknown")
            fatigue_scores = {
                "low": 95,
                "moderate": 75,
                "high": 30,
                "unknown": 60
            }
            fatigue_score = fatigue_scores.get(fatigue_level, 60)

            # Penalty for too demanding
            if fatigue_analysis.get("is_too_demanding", False):
                fatigue_score *= 0.5  # 50% penalty

            score += fatigue_score * 0.25

            # Backtracking penalty (10% weight)
            if efficiency_analysis.get("backtracking_detected", False):
                score += 30 * 0.1
            else:
                score += 90 * 0.1

        else:
            # Original scoring without fatigue analysis
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
                score += 30 * 0.1
            else:
                score += 90 * 0.1

        return round(min(100, max(0, score)), 1)

    def _get_recommended_action(self, score: float, day_recommendation: Optional[Dict] = None, fatigue_analysis: Optional[Dict] = None) -> str:
        """Get recommended action based on score, day extension needs, and fatigue analysis"""

        # Priority 1: Day extension recommendations (informational only)
        if day_recommendation and day_recommendation.get("extend_days", False):
            recommended_days = day_recommendation.get("recommended_days", "more")
            return f"ℹ️ SUGGESTION: Consider {recommended_days} days for more comfortable schedule (current plan is still acceptable)"

        # Priority 2: Fatigue concerns (now informational)
        if fatigue_analysis and fatigue_analysis.get("is_too_demanding", False):
            return "ℹ️ NOTE: Intensive schedule - Consider rest breaks for comfort"

        # Priority 3: High fatigue level (now informational)
        if fatigue_analysis and fatigue_analysis.get("fatigue_level") == "high":
            return "ℹ️ NOTE: Active schedule - Monitor energy levels and take breaks as needed"

        # Standard scoring recommendations
        if score >= 85:
            if fatigue_analysis and fatigue_analysis.get("fatigue_level") == "low":
                return "✅ ACCEPT PLAN - Excellent route optimization with manageable workload"
            else:
                return "✅ ACCEPT PLAN - Excellent route optimization"
        elif score >= 75:
            if fatigue_analysis and fatigue_analysis.get("fatigue_level") == "moderate":
                return "⚠️ ACCEPT WITH CAUTION - Good route but monitor fatigue levels"
            else:
                return "✅ ACCEPT PLAN - Good route with minor optimization opportunities"
        elif score >= 60:
            return "🔄 CONSIDER OPTIMIZATION - Route has room for improvement"
        else:
            return "🔄 OPTIMIZE ROUTE - Significant improvements needed for efficiency and safety"

    def _format_stations_for_ai(self, stations: List[Dict]) -> str:
        """Format station list for AI evaluation"""
        formatted = []
        for i, station in enumerate(stations, 1):
            name = station.get("station_name") or station.get("name", "Unknown")

            # Get distance from multiple possible fields
            distance = (station.get("distance_from_start") or
                       station.get("travel_distance_km") or
                       station.get("distance", 0))

            # Get coordinates info
            lat = station.get("latitude") or station.get("lat")
            lon = station.get("longitude") or station.get("long") or station.get("lon")
            coord_info = f" at ({lat:.4f}, {lon:.4f})" if (lat and lon) else " (no GPS)"

            formatted.append(f"{i}. {name} ({distance} km from start){coord_info}")

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