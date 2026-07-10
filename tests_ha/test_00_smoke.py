"""Smoke test: confirms the pytest-homeassistant-custom-component harness
works in this environment and can discover custom_components/portfolio_engine
at all, before trusting the more detailed tests in this package.

Discovery works via a symlink placed at
<venv>/site-packages/pytest_homeassistant_custom_component/testing_config/custom_components/portfolio_engine
pointing at the real custom_components/portfolio_engine in this repo — see
MILESTONE_2_5.md for the one-time setup command. This is the standard
pattern for testing HA custom integrations with this harness (its default
`hass` fixture always uses that package-bundled testing_config directory).
"""
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_custom_components


async def test_hass_fixture_works(hass: HomeAssistant) -> None:
    assert hass is not None


async def test_custom_component_is_discoverable(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    components = await async_get_custom_components(hass)
    assert "portfolio_engine" in components
