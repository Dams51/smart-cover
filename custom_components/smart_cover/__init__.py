"""The Smart Cover integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import (
    async_track_state_change_event,
)

from .const import (
    CONF_AUTOMATION_ID,
    CONF_OBJECT_TYPE,
    ObjectType,
    CONF_END_ENTITY,
    CONF_ENTITIES,
    CONF_PRESENCE_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    _LOGGER,
)
from .coordinator import AdaptiveDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR, Platform.BUTTON]
CONF_SUN = ["sun.sun"]


async def async_initialize_integration(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None = None,
) -> bool:
    """Initialize the integration."""

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Cover from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    object_type = entry.data.get(CONF_OBJECT_TYPE)

    # Les entrées AUTOMATION ne créent rien : elles sont juste
    # un réservoir de config lu par les entrées WINDOW
    if object_type == ObjectType.AUTOMATION:
        _LOGGER.debug("Registering automation entry %s", entry.data.get("name"))
        hass.data[DOMAIN][entry.entry_id] = entry  # on stocke l'entry elle-même
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        return True

    # Pour les entrées WINDOW, setup normal du coordinateur
    # Calculer les options fusionnées pour le tracking
    automation_id = entry.options.get(CONF_AUTOMATION_ID)
    merged = dict(entry.options)
    if automation_id:
        automation_entry = hass.config_entries.async_get_entry(automation_id)
        if automation_entry:
            merged = {**automation_entry.options, **entry.options}

    _temp_entity = merged.get(CONF_TEMP_ENTITY)
    _presence_entity = merged.get(CONF_PRESENCE_ENTITY)
    _weather_entity = merged.get(CONF_WEATHER_ENTITY)
    _cover_entities = merged.get(CONF_ENTITIES, [])
    _end_time_entity = merged.get(CONF_END_ENTITY)
    _entities = ["sun.sun"]
    for entity in [_temp_entity, _presence_entity, _weather_entity, _end_time_entity]:
        if entity is not None:
            _entities.append(entity)

    _LOGGER.debug("Setting up entry %s", entry.data.get("name"))

    coordinator = AdaptiveDataUpdateCoordinator(hass)
    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            _entities,
            coordinator.async_check_entity_state_change,
        )
    )

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            _cover_entities,
            coordinator.async_check_cover_state_change,
        )
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    if entry.data.get(CONF_OBJECT_TYPE) == ObjectType.AUTOMATION:
        # Recharger toutes les fenêtres qui référencent cette automation
        linked_windows = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.options.get(CONF_AUTOMATION_ID) == entry.entry_id
        ]
        for window_entry in linked_windows:
            await hass.config_entries.async_reload(window_entry.entry_id)
    else:
        await hass.config_entries.async_reload(entry.entry_id)
