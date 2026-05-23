from src.router import Router


def test_router_constructs():
    router = Router()

    assert router is not None


def test_weather_route():
    router = Router()

    result = router.route_message("what is the weather in Seattle")

    assert result == "weather"


def test_science_route():
    router = Router()

    result = router.route_message("how does gravity work")

    assert result == "science"


def test_general_fallback():
    router = Router()

    result = router.route_message("hello there")

    assert result == "general"
