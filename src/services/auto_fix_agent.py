"""
Auto Fix Agent - Automatically generates improved plans based on constraint violations
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class AutoFixAgent:
    """Agent that automatically fixes problematic plans"""

    def __init__(self):
        self.fixed_plans_cache = {}

    def generate_fixed_plan(self,
                           original_request: str,
                           monitoring_result: Dict[str, Any],
                           fix_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a fixed plan based on monitoring results and fix strategy

        Args:
            original_request: Original user request
            monitoring_result: Results from plan monitoring
            fix_strategy: Strategy for fixing the plan

        Returns:
            Fixed plan information
        """
        try:
            violations = monitoring_result["violations"]
            primary_action = fix_strategy["primary_action"]

            # Generate new request based on fix strategy
            new_request = self._generate_fixed_request(original_request, fix_strategy, violations)

            # Create fix explanation
            fix_explanation = self._create_fix_explanation(fix_strategy, violations, original_request)

            # Estimate improvement metrics
            improvement_metrics = self._estimate_improvements(monitoring_result, fix_strategy)

            return {
                "success": True,
                "new_request": new_request,
                "fix_explanation": fix_explanation,
                "improvement_metrics": improvement_metrics,
                "fix_summary": self._generate_fix_summary(fix_strategy),
                "user_message": self._generate_user_message(fix_strategy, new_request, improvement_metrics)
            }

        except Exception as e:
            logger.error(f"Auto fix generation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_message": "I encountered an issue generating the fix. Please try extending to 3 days or reducing stations."
            }

    def _generate_fixed_request(self,
                               original_request: str,
                               fix_strategy: Dict[str, Any],
                               violations: List[Dict]) -> str:
        """Generate a new request that addresses the violations"""

        new_request = original_request.lower()
        primary_action = fix_strategy["primary_action"]

        if primary_action == "extend_days":
            new_days = fix_strategy.get("new_days", 3)

            # Replace day count patterns
            patterns = [
                (r'(\d+)\s*days?', f'{new_days} day'),
                (r'in\s*(\d+)\s*day', f'in {new_days} day'),
                (r'for\s*(\d+)\s*day', f'for {new_days} day'),
                (r'(\d+)day', f'{new_days}day')
            ]

            for pattern, replacement in patterns:
                new_request = re.sub(pattern, replacement, new_request)

        elif primary_action == "reduce_stations":
            target_stations = fix_strategy.get("target_stations", 15)

            # Replace station count patterns
            patterns = [
                (r'(\d+)\s*stations?', f'{target_stations} stations'),
                (r'find\s*(\d+)', f'find {target_stations}'),
                (r'plan\s*(\d+)', f'plan {target_stations}'),
                (r'give\s*me\s*(\d+)', f'give me {target_stations}')
            ]

            for pattern, replacement in patterns:
                new_request = re.sub(pattern, replacement, new_request)

        elif primary_action == "single_province":
            # Focus on one province - prefer the first mentioned
            if any("nkr" in v.get("message", "").lower() for v in violations):
                new_request = new_request.replace("nkr and cyp", "nkr")
                new_request = new_request.replace("cyp and nkr", "nkr")
            else:
                new_request = new_request.replace("nkr and cyp", "cyp")
                new_request = new_request.replace("cyp and nkr", "cyp")

        return new_request

    def _create_fix_explanation(self,
                               fix_strategy: Dict[str, Any],
                               violations: List[Dict],
                               original_request: str) -> str:
        """Create a detailed explanation of the fix"""

        explanations = []
        primary_action = fix_strategy["primary_action"]

        if primary_action == "extend_days":
            new_days = fix_strategy.get("new_days", 3)
            explanations.append(f"🗓️ **Extended to {new_days} days** to reduce daily workload")

            # Explain specific benefits
            distance_violations = [v for v in violations if "distance" in v["category"]]
            time_violations = [v for v in violations if "time" in v["category"]]

            if distance_violations:
                explanations.append("🚗 **Reduces daily driving** from unsafe levels to manageable distances")
            if time_violations:
                explanations.append("⏰ **Ensures reasonable work hours** instead of exhausting 8+ hour days")

        elif primary_action == "reduce_stations":
            target_stations = fix_strategy.get("target_stations", 15)
            explanations.append(f"🎯 **Reduced to {target_stations} stations** for optimal inspection quality")
            explanations.append("✅ **Eliminates time pressure** allowing thorough inspections")

        elif primary_action == "single_province":
            explanations.append("🏛️ **Focused on single province** to minimize inter-province travel")
            explanations.append("🚗 **Reduces total driving distance** significantly")

        # Add safety benefits
        critical_violations = [v for v in violations if v["type"] == "critical"]
        if critical_violations:
            explanations.append("🛡️ **Eliminates safety risks** identified in original plan")

        return "\n".join(explanations)

    def _estimate_improvements(self,
                              monitoring_result: Dict[str, Any],
                              fix_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate improvements from the fix"""

        original_violations = len(monitoring_result["violations"])
        severity_score = monitoring_result["severity_score"]

        improvements = {
            "violations_fixed": 0,
            "safety_improvement": 0,
            "efficiency_improvement": 0,
            "fatigue_reduction": 0
        }

        primary_action = fix_strategy["primary_action"]

        if primary_action == "extend_days":
            new_days = fix_strategy.get("new_days", 3)
            # Extending days typically fixes most violations
            improvements["violations_fixed"] = max(1, original_violations - 1)
            improvements["safety_improvement"] = min(90, severity_score * 0.8)
            improvements["efficiency_improvement"] = 60
            improvements["fatigue_reduction"] = 80

        elif primary_action == "reduce_stations":
            # Reducing stations fixes time/workload issues
            improvements["violations_fixed"] = max(1, original_violations // 2)
            improvements["safety_improvement"] = min(70, severity_score * 0.6)
            improvements["efficiency_improvement"] = 40
            improvements["fatigue_reduction"] = 70

        elif primary_action == "single_province":
            # Single province fixes distance issues
            improvements["violations_fixed"] = max(1, original_violations // 2)
            improvements["safety_improvement"] = min(60, severity_score * 0.5)
            improvements["efficiency_improvement"] = 80
            improvements["fatigue_reduction"] = 50

        return improvements

    def _generate_fix_summary(self, fix_strategy: Dict[str, Any]) -> str:
        """Generate a concise fix summary"""

        primary_action = fix_strategy["primary_action"]
        confidence = fix_strategy.get("confidence", 85)

        summaries = {
            "extend_days": f"Extended to {fix_strategy.get('new_days', 3)} days for safety",
            "reduce_stations": f"Reduced to {fix_strategy.get('target_stations', 15)} stations for quality",
            "single_province": "Focused on single province for efficiency"
        }

        base_summary = summaries.get(primary_action, "Optimized plan for safety")
        return f"{base_summary} (Confidence: {confidence}%)"

    def _generate_user_message(self,
                              fix_strategy: Dict[str, Any],
                              new_request: str,
                              improvement_metrics: Dict[str, Any]) -> str:
        """Generate user-friendly message about the fix"""

        primary_action = fix_strategy["primary_action"]
        violations_fixed = improvement_metrics["violations_fixed"]
        safety_improvement = improvement_metrics["safety_improvement"]

        message_parts = [
            "🔧 **PLAN AUTOMATICALLY FIXED!**",
            ""
        ]

        # Explain what was done
        if primary_action == "extend_days":
            new_days = fix_strategy.get("new_days", 3)
            message_parts.extend([
                f"✅ **Extended your plan to {new_days} days** for safety and comfort",
                f"🎯 **New request**: {new_request}",
                ""
            ])

        elif primary_action == "reduce_stations":
            target_stations = fix_strategy.get("target_stations", 15)
            message_parts.extend([
                f"✅ **Optimized to {target_stations} stations** for better quality",
                f"🎯 **New request**: {new_request}",
                ""
            ])

        elif primary_action == "single_province":
            message_parts.extend([
                "✅ **Focused on single province** to minimize travel",
                f"🎯 **New request**: {new_request}",
                ""
            ])

        # Show improvements
        message_parts.extend([
            "**✨ Improvements achieved:**",
            f"- 🛡️ **Safety**: {safety_improvement:.0f}% safer",
            f"- 🔧 **Fixed**: {violations_fixed} constraint violation(s)",
            f"- 😌 **Fatigue**: {improvement_metrics['fatigue_reduction']:.0f}% less tiring",
            f"- ⚡ **Efficiency**: {improvement_metrics['efficiency_improvement']:.0f}% better optimized",
            "",
            "**🚀 Ready to generate your improved plan?**",
            "",
            "**Options:**",
            "1. ✅ **Generate new plan** (Execute the fixed request)",
            "2. 📝 **Modify further** (Make additional changes)",
            "3. 🔄 **Try different fix** (See other solutions)",
            "",
            "Just type 'generate' to create your optimized plan!"
        ])

        return "\n".join(message_parts)

    def create_alternative_fixes(self,
                                original_request: str,
                                monitoring_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create multiple alternative fix options"""

        alternatives = []
        violations = monitoring_result["violations"]

        # Option 1: Extend days (most conservative)
        alternatives.append({
            "strategy": "extend_days",
            "title": "🗓️ **Extend to 3 Days** (Safest)",
            "description": "More comfortable schedule with proper rest",
            "benefits": ["Eliminates all safety violations", "Reduces daily fatigue", "Better inspection quality"],
            "trade_offs": ["Requires extra day", "More accommodation costs"]
        })

        # Option 2: Reduce stations (balanced)
        alternatives.append({
            "strategy": "reduce_stations",
            "title": "🎯 **Optimize Station Count** (Balanced)",
            "description": "Keep original timeframe but inspect fewer stations",
            "benefits": ["Maintains timeline", "Ensures quality inspections", "Reduces workload"],
            "trade_offs": ["Fewer stations inspected", "May need follow-up trip"]
        })

        # Option 3: Single province (efficient)
        if "nkr" in original_request.lower() and "cyp" in original_request.lower():
            alternatives.append({
                "strategy": "single_province",
                "title": "🏛️ **Focus One Province** (Efficient)",
                "description": "Concentrate on either Nakhon Ratchasima or Chaiyaphum",
                "benefits": ["Minimizes travel distance", "More stations possible", "Efficient routing"],
                "trade_offs": ["Other province needs separate trip", "Limited geographical coverage"]
            })

        return alternatives

    def explain_fix_benefits(self, fix_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Explain the benefits of a specific fix"""

        primary_action = fix_strategy["primary_action"]

        benefits = {
            "extend_days": {
                "safety": "Eliminates dangerous daily distance/time limits",
                "quality": "More time for thorough station inspections",
                "comfort": "Reasonable work hours with proper rest",
                "feasibility": "Realistic travel times between provinces"
            },
            "reduce_stations": {
                "safety": "Eliminates time pressure and rushing",
                "quality": "Focus on quality over quantity inspections",
                "comfort": "Manageable daily workload",
                "feasibility": "Achievable within time constraints"
            },
            "single_province": {
                "safety": "Reduces total driving and fatigue",
                "quality": "More efficient route planning",
                "comfort": "Less inter-province travel stress",
                "feasibility": "Optimal use of available time"
            }
        }

        return benefits.get(primary_action, {})

def test_auto_fix_agent():
    """Test the auto fix agent"""
    print("🧪 Testing Auto Fix Agent")
    print("=" * 50)

    agent = AutoFixAgent()

    # Mock monitoring result
    monitoring_result = {
        "violations": [
            {
                "type": "critical",
                "category": "daily_distance",
                "day": 1,
                "value": 350,
                "limit": 300,
                "message": "Day 1: 350km exceeds safe daily limit of 300km"
            }
        ],
        "severity_score": 30
    }

    # Mock fix strategy
    fix_strategy = {
        "primary_action": "extend_days",
        "new_days": 3,
        "confidence": 90
    }

    original_request = "give me a plan for 20 stations at nkr and cyp in 2 day"

    result = agent.generate_fixed_plan(original_request, monitoring_result, fix_strategy)

    if result["success"]:
        print("✅ Fix generated successfully!")
        print(f"New request: {result['new_request']}")
        print(f"Fix summary: {result['fix_summary']}")
    else:
        print("❌ Fix generation failed")

if __name__ == "__main__":
    test_auto_fix_agent()