from src.router import Router


def test_router_constructs():
    router = Router(
        agent_capabilities={
            "weather_agent": ["weather", "temperature", "forecast"],
            "science": ["why", "how does", "what is"],
        }
    )

    assert router is not None


def test_weather_route():
    router = Router(
        agent_capabilities={
            "weather_agent": ["weather", "temperature", "forecast"],
        }
    )

    agent, confidence = router.route_message("what is the weather in Seattle")

    assert agent == "weather_agent"
    assert confidence > 0


def test_science_route():
    router = Router(
        agent_capabilities={
            "science": ["why", "how does", "what is"],
        }
    )

    agent, confidence = router.route_message("how does gravity work")

    assert agent == "science"
    assert confidence > 0


def test_general_fallback():
    router = Router(
        agent_capabilities={
            "weather_agent": ["weather"],
        }
    )

    agent, confidence = router.route_message("hello there")

    assert agent == "general"
    assert confidence == 0.0
