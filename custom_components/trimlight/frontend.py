"""Serve the pattern card bundled with HACS integration downloads."""
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

CARD_URL = "/trimlight/trimlight-pattern-card.js"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register once at integration setup, independently of cloud connectivity."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            CARD_URL,
            str(Path(__file__).parent / "frontend" / "trimlight-pattern-card.js"),
            False,
        )
    ])
