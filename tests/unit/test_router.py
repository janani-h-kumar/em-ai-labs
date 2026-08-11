from src.agents.agent_descriptor import AgentDescriptor
from src.agents.base_agent import BaseAgent
from src.router import MessageRouter, RoutingResult


class DummyAgent(BaseAgent):
    def initialize(self):
        pass

    async def handle(self, task, context):
        return ""


def descriptor(name: str, capabilities: list[str]) -> AgentDescriptor:
    return AgentDescriptor(
        name=name,
        description="test agent",
        capabilities=capabilities,
        agent_class=DummyAgent,
    )


def test_router_constructs():
    router = MessageRouter(
        descriptors=[
            descriptor("weather_agent", ["weather", "temperature", "forecast"]),
            descriptor("science", ["why", "how does", "what is"]),
        ]
    )

    assert router is not None


def test_weather_route():
    router = MessageRouter(
        descriptors=[
            descriptor("weather_agent", ["weather", "temperature", "forecast"]),
        ]
    )

    result = router.route_message("what is the weather in Seattle")

    assert isinstance(result, RoutingResult)
    assert result.agent_name == "weather_agent"
    assert result.confidence > 0


def test_science_route():
    router = MessageRouter(
        descriptors=[
            descriptor("science", ["why", "how does", "what is"]),
        ]
    )

    result = router.route_message("how does gravity work")

    assert isinstance(result, RoutingResult)
    assert result.agent_name == "science"
    assert result.confidence > 0


def test_general_fallback():
    router = MessageRouter(
        descriptors=[
            descriptor("weather_agent", ["weather"]),
        ]
    )

    result = router.route_message("hello there")

    assert result.agent_name == "general"
    assert result.confidence == 0.0
