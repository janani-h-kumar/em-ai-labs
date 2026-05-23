from src.router import MessageRouter


def test_router_constructs():
    router = MessageRouter()
    assert router is not None
