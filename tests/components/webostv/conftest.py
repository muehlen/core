"""Common fixtures and objects for the LG webOS integration tests."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.webostv.const import LIVE_TV_APP_ID

from . import CHANNEL_1, CHANNEL_2

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": "some-fake-uuid"}
        client.software_info = {"major_ver": "major", "minor_ver": "minor"}
        client.system_info = {"modelName": "TVFAKE"}
        client.client_key = "0123456789"
        client.apps = {
            LIVE_TV_APP_ID: {
                "title": "Live TV",
                "id": LIVE_TV_APP_ID,
                "largeIcon": "large-icon",
                "icon": "icon",
            },
        }
        client.inputs = {
            "in1": {"label": "Input01", "id": "in1", "appId": "app0"},
            "in2": {"label": "Input02", "id": "in2", "appId": "app1"},
        }
        client.current_app_id = LIVE_TV_APP_ID

        client.channels = [CHANNEL_1, CHANNEL_2]
        client.current_channel = CHANNEL_1

        client.volume = 37
        client.sound_output = "speaker"
        client.muted = False
        client.is_on = True

        async def mock_state_update_callback():
            await client.register_state_update_callback.call_args[0][0](client)

        client.mock_state_update = AsyncMock(side_effect=mock_state_update_callback)

        yield client
