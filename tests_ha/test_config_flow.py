"""Config flow tests — real ConfigFlow against the real hass fixture."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portfolio_engine.const import (
    CONF_INVESTMENTS_PATH,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)


async def test_user_flow_creates_entry_when_path_exists(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: investments_dir.path,
            CONF_UPDATE_INTERVAL_MINUTES: 15,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INVESTMENTS_PATH] == investments_dir.path
    assert result["data"][CONF_UPDATE_INTERVAL_MINUTES] == 15

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_user_flow_shows_error_when_path_missing(
    hass: HomeAssistant, enable_custom_integrations: None, tmp_path
) -> None:
    nonexistent_path = str(tmp_path / "does_not_exist")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INVESTMENTS_PATH: nonexistent_path,
            CONF_UPDATE_INTERVAL_MINUTES: 15,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "investments_path_not_found"


async def test_second_setup_is_aborted_as_already_configured(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    investments_dir.write_portfolio()

    async def _run_flow():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        return await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_INVESTMENTS_PATH: investments_dir.path,
                CONF_UPDATE_INTERVAL_MINUTES: 15,
            },
        )

    first = await _run_flow()
    assert first["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    second = await _run_flow()
    assert second["type"] == data_entry_flow.FlowResultType.ABORT
    assert second["reason"] == "already_configured"


async def test_update_interval_below_minimum_is_rejected(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir
) -> None:
    investments_dir.write_portfolio()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # The voluptuous schema (vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES))
    # rejects an out-of-range value before the flow's own step logic runs.
    # HA's flow manager surfaces that as a raised InvalidData rather than a
    # FORM re-render with an "errors" dict - both are valid ways for this to
    # manifest depending on HA version, so either counts as confirming
    # enforcement; only a successful CREATE_ENTRY would be the real bug.
    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 1},
        )
    except data_entry_flow.InvalidData:
        return  # enforcement confirmed via raised validation error

    assert result["type"] == data_entry_flow.FlowResultType.FORM, (
        "update_interval_minutes=1 was accepted; MIN_UPDATE_INTERVAL_MINUTES is not enforced"
    )


# --- Milestone 10: multiple config entries, different investments paths ------

async def test_two_entries_with_different_paths_can_both_be_set_up(
    hass: HomeAssistant, enable_custom_integrations: None, tmp_path, mock_price_provider
) -> None:
    """The original design's unique_id was a fixed domain-wide constant,
    blocking a second entry from ever existing regardless of path. Fixed
    in Milestone 10 - unique_id is now the investments_path itself, so two
    genuinely different setups are both allowed.
    """
    import yaml

    path_a = tmp_path / "investments_a"
    path_b = tmp_path / "investments_b"
    for path in (path_a, path_b):
        portfolio_dir = path / "demo_portfolio"
        portfolio_dir.mkdir(parents=True)
        (portfolio_dir / "holdings.yaml").write_text(
            yaml.safe_dump(
                {
                    "name": "Demo",
                    "base_currency": "USD",
                    "cash_balance": 1000.0,
                    "holdings": [],
                }
            )
        )

    async def _run_flow(path_str):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        return await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_INVESTMENTS_PATH: path_str, CONF_UPDATE_INTERVAL_MINUTES: 15},
        )

    first = await _run_flow(str(path_a))
    assert first["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    second = await _run_flow(str(path_b))
    assert second["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reconfigure_updates_investments_path_in_place(
    hass: HomeAssistant, enable_custom_integrations: None, investments_dir, mock_price_provider
) -> None:
    import yaml

    investments_dir.write_portfolio()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INVESTMENTS_PATH: investments_dir.path, CONF_UPDATE_INTERVAL_MINUTES: 15},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    original_entry_id = entry.entry_id

    # a second, different investments folder to reconfigure onto
    new_root = investments_dir._root.parent / "investments_v2"
    new_portfolio_dir = new_root / "demo_portfolio"
    new_portfolio_dir.mkdir(parents=True)
    (new_portfolio_dir / "holdings.yaml").write_text(
        yaml.safe_dump(
            {"name": "Demo", "base_currency": "USD", "cash_balance": 2000.0, "holdings": []}
        )
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INVESTMENTS_PATH: str(new_root), CONF_UPDATE_INTERVAL_MINUTES: 20},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # same entry_id preserved - Store-backed history keyed by entry_id is unaffected
    updated_entry = hass.config_entries.async_get_entry(original_entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_INVESTMENTS_PATH] == str(new_root)
    assert updated_entry.data[CONF_UPDATE_INTERVAL_MINUTES] == 20

    # confirm it actually picked up the new portfolio's data (cash_balance=2000)
    state = hass.states.get("sensor.demo_portfolio_cash_balance")
    assert state.state == "2000.0"

    await hass.config_entries.async_unload(original_entry_id)
    await hass.async_block_till_done()
