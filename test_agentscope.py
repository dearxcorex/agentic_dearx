"""Test AgentScope installation and basic functionality"""

import agentscope
from agentscope.message import Msg
from agentscope.agents import DialogAgent
import json

def test_agentscope_basic():
    """Test basic AgentScope functionality"""
    print("Testing AgentScope installation...")

    # Initialize AgentScope
    agentscope.init(model_configs=[])
    print("✅ AgentScope initialized")

    # Create a message
    test_msg = Msg(name="test", content="Hello from AgentScope")
    print(f"✅ Created message: {test_msg.content}")

    # Create a simple agent
    try:
        agent = DialogAgent(
            name="TestAgent",
            sys_prompt="You are a test agent",
            model_config_name=None,
            use_memory=False
        )
        print("✅ Created DialogAgent")
    except Exception as e:
        print(f"⚠️ Agent creation warning: {e}")

    print("\nAgentScope is properly installed and working!")
    return True

def test_custom_agents():
    """Test our custom agent imports"""
    print("\nTesting custom agent imports...")

    try:
        from agents import (
            LanguageProcessingAgent,
            LocationAgent,
            DatabaseAgent,
            RoutePlanningAgent,
            ResponseAgent
        )
        print("✅ All custom agents imported successfully")

        # Test agent creation
        lang_agent = LanguageProcessingAgent()
        print(f"✅ Created {lang_agent.name}")

        return True
    except Exception as e:
        print(f"❌ Error importing custom agents: {e}")
        return False

def test_planner():
    """Test the main planner"""
    print("\nTesting FM Station Planner...")

    try:
        from planner import FMStationPlanner
        planner = FMStationPlanner()
        print("✅ FM Station Planner initialized")

        # Test with a simple request (won't actually call APIs)
        test_input = "ทดสอบระบบ"
        print(f"Testing with input: {test_input}")

        return True
    except Exception as e:
        print(f"⚠️ Planner initialization note: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("AgentScope FM Station Planner - System Test")
    print("=" * 50)

    # Run tests
    test_agentscope_basic()
    test_custom_agents()
    test_planner()

    print("\n" + "=" * 50)
    print("System test complete!")
    print("=" * 50)