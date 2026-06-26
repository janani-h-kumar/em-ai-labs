from unittest.mock import patch

from src import main


def test_main_module_imports():
    assert main is not None


@patch("src.main.ApplicationService")
def test_create_application_service(mock_application_service):
    application_service = main.ApplicationService("config.yaml")

    assert application_service is not None
