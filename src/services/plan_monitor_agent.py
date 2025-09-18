"""
Plan Monitor Agent - Proactively detects constraint violations and offers fixes
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..services.openrouter_client import OpenRouterClient
from ..config.config import Config

logger = logging.getLogger(__name__)

class PlanMonitorAgent:
    """Agent that monitors plans for constraint violations and offers automatic fixes"""

    def __init__(self):
        self.llm_client = OpenRouterClient()

        # Constraint thresholds
        self.MAX_DAILY_DISTANCE_KM = 300
        self.MAX_DAILY_TIME_MINUTES = 480  # 8 hours
        self.MAX_TOTAL_DISTANCE_2_DAYS = 500
        self.MAX_STATIONS_PER_DAY = 15
        self.OPTIMAL_DAILY_DISTANCE = 250
        self.OPTIMAL_DAILY_TIME = 420  # 7 hours

    def monitor_plan_constraints(self,
                                daily_plans: List[Dict],
                                requested_stations: int,
                                requested_days: int,
                                user_request: str) -> Dict[str, Any]:
        """
        Monitor plan for constraint violations and generate intervention recommendations

        Args:
            daily_plans: List of daily plan dictionaries
            requested_stations: Number of stations originally requested
            requested_days: Number of days originally requested
            user_request: Original user request text

        Returns:
            Monitoring result with intervention recommendations
        """
        violations = []
        severity_score = 0
        intervention_needed = False

        # Check daily constraints
        for i, plan in enumerate(daily_plans, 1):
            daily_distance = plan.get("total_distance_km", 0)
            daily_time = plan.get("total_time_minutes", 0)
            daily_stations = len(plan.get("stations", []))

            # Critical violations (immediate intervention needed)
            if daily_distance > self.MAX_DAILY_DISTANCE_KM:
                violations.append({
                    "type": "critical",
                    "category": "daily_distance",
                    "day": i,
                    "value": daily_distance,
                    "limit": self.MAX_DAILY_DISTANCE_KM,
                    "message": f"Day {i}: {daily_distance:.1f}km exceeds safe daily limit of {self.MAX_DAILY_DISTANCE_KM}km"
                })
                severity_score += 30
                intervention_needed = True

            if daily_time > self.MAX_DAILY_TIME_MINUTES:
                violations.append({
                    "type": "critical",
                    "category": "daily_time",
                    "day": i,
                    "value": daily_time,
                    "limit": self.MAX_DAILY_TIME_MINUTES,
                    "message": f"Day {i}: {daily_time/60:.1f} hours exceeds safe daily limit of {self.MAX_DAILY_TIME_MINUTES/60:.1f} hours"
                })
                severity_score += 25
                intervention_needed = True

            # Warning level violations
            if daily_distance > self.OPTIMAL_DAILY_DISTANCE:
                violations.append({
                    "type": "warning",
                    "category": "suboptimal_distance",
                    "day": i,
                    "value": daily_distance,
                    "limit": self.OPTIMAL_DAILY_DISTANCE,
                    "message": f"Day {i}: {daily_distance:.1f}km above optimal daily distance of {self.OPTIMAL_DAILY_DISTANCE}km"
                })
                severity_score += 10

            if daily_stations > self.MAX_STATIONS_PER_DAY:
                violations.append({
                    "type": "warning",
                    "category": "too_many_stations",
                    "day": i,
                    "value": daily_stations,
                    "limit": self.MAX_STATIONS_PER_DAY,
                    "message": f"Day {i}: {daily_stations} stations may cause fatigue (recommended max: {self.MAX_STATIONS_PER_DAY})"
                })
                severity_score += 15

        # Check total constraints
        total_distance = sum(plan.get("total_distance_km", 0) for plan in daily_plans)
        actual_stations = sum(len(plan.get("stations", [])) for plan in daily_plans)

        if requested_days == 2 and total_distance > self.MAX_TOTAL_DISTANCE_2_DAYS:
            violations.append({
                "type": "critical",
                "category": "total_distance",
                "value": total_distance,
                "limit": self.MAX_TOTAL_DISTANCE_2_DAYS,
                "message": f"Total distance {total_distance:.1f}km exceeds 2-day limit of {self.MAX_TOTAL_DISTANCE_2_DAYS}km"
            })
            severity_score += 20
            intervention_needed = True

        # Station shortfall check
        if requested_stations > actual_stations:
            shortfall = requested_stations - actual_stations
            violations.append({
                "type": "warning",
                "category": "station_shortfall",
                "value": actual_stations,
                "limit": requested_stations,
                "message": f"Only {actual_stations}/{requested_stations} stations planned due to time constraints"
            })
            severity_score += shortfall * 2

        return {
            "intervention_needed": intervention_needed,
            "severity_score": severity_score,
            "violations": violations,
            "total_distance": total_distance,
            "actual_stations": actual_stations,
            "violation_summary": self._generate_violation_summary(violations),
            "fix_recommendations": self._generate_fix_recommendations(violations, requested_stations, requested_days, user_request)
        }

    def generate_intervention_message(self, monitoring_result: Dict[str, Any]) -> str:
        """Generate user-friendly intervention message"""

        violations = monitoring_result["violations"]
        severity_score = monitoring_result["severity_score"]

        if not violations:
            return None  # No intervention needed

        # Critical violations require immediate intervention
        critical_violations = [v for v in violations if v["type"] == "critical"]

        if critical_violations:
            message_parts = [
                "⚠️ **PLAN SAFETY WARNING** ⚠️",
                "",
                "I need to interrupt this plan because it exceeds safety limits:",
                ""
            ]

            for violation in critical_violations:
                message_parts.append(f"🚨 {violation['message']}")

            message_parts.extend([
                "",
                "**This plan could cause:**",
                "- Inspector fatigue and safety risks",
                "- Poor inspection quality due to rushing",
                "- Potential vehicle breakdown from overuse",
                "- Difficulty returning home safely by 17:00",
                "",
                "🤖 **Let me automatically fix this plan for you!**",
                "",
                "**Would you like me to:**",
                "1. 🔧 **Auto-fix the plan** (I'll optimize it automatically)",
                "2. 📋 **See fix options** (Show me different solutions)",
                "3. ✅ **Accept risks** (Keep the dangerous plan anyway)",
                "",
                "**Quick response:** Just type 'fix it' and I'll handle everything!"
            ])

        else:
            # Warning level violations
            message_parts = [
                "💡 **PLAN OPTIMIZATION NOTICE**",
                "",
                "Your plan has some optimization opportunities:",
                ""
            ]

            warning_violations = [v for v in violations if v["type"] == "warning"]
            for violation in warning_violations[:3]:  # Show top 3 warnings
                message_parts.append(f"⚡ {violation['message']}")

            message_parts.extend([
                "",
                "🤖 **I can optimize this plan for better efficiency!**",
                "",
                "**Options:**",
                "1. 🔧 **Auto-optimize** (I'll improve it automatically)",
                "2. 📋 **Keep current plan** (It's still workable)",
                "",
                "Type 'optimize' for automatic improvements!"
            ])

        return "\n".join(message_parts)

    def auto_fix_plan(self,
                     monitoring_result: Dict[str, Any],
                     original_request: str,
                     daily_plans: List[Dict]) -> Dict[str, Any]:
        """
        Automatically generate a fixed plan using AI

        Args:
            monitoring_result: Results from plan monitoring
            original_request: Original user request
            daily_plans: Current daily plans

        Returns:
            Fixed plan recommendations
        """
        try:
            violations = monitoring_result["violations"]
            critical_violations = [v for v in violations if v["type"] == "critical"]

            # Determine fix strategy based on violations
            fix_strategy = self._determine_fix_strategy(violations, daily_plans)

            # Generate AI-powered fix recommendations
            ai_recommendations = self._get_ai_fix_recommendations(
                violations, original_request, daily_plans, fix_strategy
            )

            return {
                "success": True,
                "fix_strategy": fix_strategy,
                "ai_recommendations": ai_recommendations,
                "new_request_suggestions": self._generate_new_request_suggestions(fix_strategy, original_request),
                "fix_explanation": self._explain_fixes(fix_strategy, violations)
            }

        except Exception as e:
            logger.error(f"Auto-fix plan error: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_suggestions": [
                    "Extend to 3 days for safer schedule",
                    "Reduce to single province (ชัยภูมิ or นครราชสีมา)",
                    "Reduce station count to 15 stations max"
                ]
            }

    def _determine_fix_strategy(self, violations: List[Dict], daily_plans: List[Dict]) -> Dict[str, Any]:
        """Determine the best fix strategy based on violations"""

        critical_count = len([v for v in violations if v["type"] == "critical"])
        total_distance = sum(plan.get("total_distance_km", 0) for plan in daily_plans)

        strategy = {
            "primary_action": "extend_days",
            "secondary_actions": [],
            "confidence": 85
        }

        # If multiple critical violations, extend days
        if critical_count >= 2:
            strategy["primary_action"] = "extend_days"
            strategy["new_days"] = len(daily_plans) + 1
            strategy["confidence"] = 90

        # If only distance violations, try reducing stations first
        elif any(v["category"] in ["daily_distance", "total_distance"] for v in violations):
            if total_distance > 600:
                strategy["primary_action"] = "extend_days"
                strategy["new_days"] = 3
            else:
                strategy["primary_action"] = "reduce_stations"
                strategy["target_stations"] = max(12, len(daily_plans) * 6)

        # If time violations, extend days or start earlier
        elif any(v["category"] == "daily_time" for v in violations):
            strategy["primary_action"] = "extend_days"
            strategy["new_days"] = len(daily_plans) + 1
            strategy["secondary_actions"].append("earlier_start")

        # Add secondary optimizations
        if total_distance > 400:
            strategy["secondary_actions"].append("optimize_route")

        return strategy

    def _get_ai_fix_recommendations(self,
                                   violations: List[Dict],
                                   original_request: str,
                                   daily_plans: List[Dict],
                                   fix_strategy: Dict) -> str:
        """Get AI-generated fix recommendations"""

        try:
            model_config = Config.get_model("complex_reasoning")

            violations_summary = "\n".join([f"- {v['message']}" for v in violations[:5]])

            prompt = f"""As an FM station inspection planning expert, analyze this problematic plan and provide specific fix recommendations:

ORIGINAL REQUEST: {original_request}

CURRENT PLAN VIOLATIONS:
{violations_summary}

CURRENT PLAN SUMMARY:
- Days: {len(daily_plans)}
- Total Distance: {sum(plan.get('total_distance_km', 0) for plan in daily_plans):.1f} km
- Total Stations: {sum(len(plan.get('stations', [])) for plan in daily_plans)}
- Stations per day: {[len(plan.get('stations', [])) for plan in daily_plans]}

RECOMMENDED FIX STRATEGY: {fix_strategy['primary_action']}

Provide a specific, actionable fix recommendation in 2-3 sentences that:
1. Addresses the safety violations
2. Maintains inspection quality
3. Gives the user confidence in the new plan

Focus on practical benefits for the field inspector."""

            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client._make_request(messages, model_config)

            if response and "choices" in response:
                return response["choices"][0]["message"]["content"].strip()
            else:
                return "Extending to more days will create a safer, more manageable inspection schedule."

        except Exception as e:
            logger.error(f"AI fix recommendations failed: {e}")
            return "I recommend extending to more days for a safer inspection schedule."

    def _generate_new_request_suggestions(self, fix_strategy: Dict, original_request: str) -> List[str]:
        """Generate new request suggestions based on fix strategy"""

        suggestions = []

        if fix_strategy["primary_action"] == "extend_days":
            new_days = fix_strategy.get("new_days", 3)
            # Replace day count in original request
            modified_request = original_request.replace("2 day", f"{new_days} day")
            modified_request = modified_request.replace("2days", f"{new_days}days")
            if "2" in original_request and "day" in original_request:
                modified_request = original_request.replace("2", str(new_days), 1)
            suggestions.append(f"📅 **{new_days} days**: {modified_request}")

        elif fix_strategy["primary_action"] == "reduce_stations":
            target_stations = fix_strategy.get("target_stations", 15)
            modified_request = original_request
            # Replace station count
            import re
            modified_request = re.sub(r'\d+\s*stations?', f"{target_stations} stations", modified_request)
            suggestions.append(f"🎯 **Reduced stations**: {modified_request}")

        # Add single province options
        if "nkr" in original_request.lower() and "cyp" in original_request.lower():
            suggestions.append("🏛️ **Focus on นครราชสีมา only**: " + original_request.replace("nkr and cyp", "nkr"))
            suggestions.append("🏛️ **Focus on ชัยภูมิ only**: " + original_request.replace("nkr and cyp", "cyp"))

        return suggestions

    def _explain_fixes(self, fix_strategy: Dict, violations: List[Dict]) -> str:
        """Explain why these fixes will solve the problems"""

        explanations = []

        if fix_strategy["primary_action"] == "extend_days":
            explanations.append(f"🗓️ **Extending to {fix_strategy.get('new_days', 3)} days** reduces daily distance and time pressure")

        elif fix_strategy["primary_action"] == "reduce_stations":
            explanations.append("🎯 **Reducing station count** eliminates time pressure and distance violations")

        # Explain specific violation fixes
        critical_violations = [v for v in violations if v["type"] == "critical"]
        if critical_violations:
            explanations.append("⚡ **Eliminates safety violations** that could cause inspector fatigue")

        if any("distance" in v["category"] for v in violations):
            explanations.append("🚗 **Reduces driving burden** for safer travel")

        if any("time" in v["category"] for v in violations):
            explanations.append("⏰ **Ensures reasonable work hours** for quality inspections")

        return " • ".join(explanations)

    def _generate_violation_summary(self, violations: List[Dict]) -> str:
        """Generate a summary of violations"""
        if not violations:
            return "No violations detected"

        critical_count = len([v for v in violations if v["type"] == "critical"])
        warning_count = len([v for v in violations if v["type"] == "warning"])

        summary_parts = []
        if critical_count > 0:
            summary_parts.append(f"{critical_count} critical safety violation(s)")
        if warning_count > 0:
            summary_parts.append(f"{warning_count} optimization opportunity(ies)")

        return ", ".join(summary_parts)

    def _generate_fix_recommendations(self,
                                    violations: List[Dict],
                                    requested_stations: int,
                                    requested_days: int,
                                    user_request: str) -> List[str]:
        """Generate specific fix recommendations"""

        recommendations = []

        critical_violations = [v for v in violations if v["type"] == "critical"]

        if critical_violations:
            # Critical fixes needed
            if any("distance" in v["category"] for v in critical_violations):
                recommendations.append(f"Extend to {requested_days + 1} days to reduce daily driving")
                recommendations.append("Focus on single province to minimize travel")

            if any("time" in v["category"] for v in critical_violations):
                recommendations.append("Reduce stations per day to manageable levels")
                recommendations.append("Start earlier (08:00) if possible")

        else:
            # Optimization recommendations
            recommendations.append("Consider 3-day schedule for more comfort")
            recommendations.append("Optimize route sequence")
            recommendations.append("Add buffer time for unexpected delays")

        return recommendations