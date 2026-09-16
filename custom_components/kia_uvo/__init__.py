import asyncio
import hashlib
import logging
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as importlib_version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.loader import DATA_COMPONENTS, async_get_integration

from .const import (
    BRANDS,
    CONF_BRAND,
    CONF_ENABLE_GEOLOCATION_ENTITY,
    CONF_FORCE_REFRESH_INTERVAL,
    CONF_LIBRARY_OVERRIDE,
    CONF_NO_FORCE_REFRESH_HOUR_FINISH,
    CONF_NO_FORCE_REFRESH_HOUR_START,
    CONF_USE_EMAIL_WITH_GEOCODE_API,
    DEFAULT_PIN,
    DOMAIN,
    LIB_PACKAGE_NAME,
    OVERRIDE_APPLIED_KEY,
    REGIONS,
)
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.IMAGE,
    Platform.TIME,
]


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    return True


def _get_installed_library_version() -> str | None:
    """Return the installed library version, or None when not installed."""
    try:
        return importlib_version(LIB_PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def _build_version_target(value: str, requirement: str | None) -> str:
    """Rebuild the manifest requirement with the requested version.

    "4.28.0" and "==4.28.0" both become "<manifest-base>==4.28.0", keeping
    any extras from the manifest (e.g. [image]).
    """
    requested = value.removeprefix("==")
    base_spec = requirement.rsplit("==", 1)[0] if requirement else LIB_PACKAGE_NAME
    return f"{base_spec}=={requested}"


async def _async_install_library_override(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Install the library version requested in the integration options.

    The value comes from entry.options["library_override"] (options flow):
    empty means the manifest-pinned version, anything else is interpreted by
    _build_override_target.

    On a version change (or every start for a git/URL spec) the override is
    pip-installed, the loaded library and integration modules are purged so
    the setup retry imports the fresh library, then ConfigEntryNotReady is
    raised. A failed install also raises ConfigEntryNotReady so HA retries
    with the pinned version.

    The library is a single site-packages install shared by all kia_uvo
    entries: the first entry whose setup installs an override wins, and an
    entry requesting a different override this session only logs a warning.
    """
    value = str(config_entry.options.get(CONF_LIBRARY_OVERRIDE) or "").strip()
    if not value:
        return

    installed = await hass.async_add_executor_job(_get_installed_library_version)

    if any(ch in value for ch in "@/:"):
        # A verbatim pip requirement (git+https, file://, ...): pip reports a
        # spec resolving to the already-installed version as satisfied, so
        # force the package swap. --no-deps keeps dependency installs out of
        # every start/reload.
        target_spec = value
        pip_args = ["--force-reinstall", "--no-deps"]
    else:
        # A bare version or "==" pin: no-op when already installed, else
        # rebuild the manifest requirement with the requested version
        # (keeping extras such as [image]).
        if installed == value.removeprefix("=="):
            return
        integration = await async_get_integration(hass, DOMAIN)
        requirement = next(
            (
                req
                for req in integration.manifest["requirements"]
                if str(req).startswith(LIB_PACKAGE_NAME)
            ),
            None,
        )
        target_spec = _build_version_target(value, requirement)
        pip_args = []

    # The library install is global; a second entry must not fight over pip.
    applied = hass.data.get(OVERRIDE_APPLIED_KEY)
    if applied is not None:
        if applied != target_spec:
            _LOGGER.warning(
                "Library override %s requested by this config entry, but %s "
                "is already active (set by another entry) — ignoring",
                target_spec,
                applied,
            )
        return

    _LOGGER.warning(
        "[kia_uvo] VERSION OVERRIDE: %s requested, but %s is installed. "
        "Attempting to install override...",
        target_spec,
        installed or "not installed",
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        *pip_args,
        target_spec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    _stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        _LOGGER.error(
            "[kia_uvo] VERSION OVERRIDE: pip install %s failed (%s): %s",
            target_spec,
            proc.returncode,
            _stdout.decode(errors="replace"),
        )
        raise ConfigEntryNotReady(f"Library override install failed ({target_spec})")

    # Drop the loaded library and integration modules so the setup retry
    # re-imports both from disk (the library binding in coordinator.py is
    # created at import time and would otherwise keep the old version).
    for module_name in [
        name
        for name in sys.modules
        if name.startswith(
            (LIB_PACKAGE_NAME, f"{LIB_PACKAGE_NAME}.", "custom_components.kia_uvo")
        )
    ]:
        del sys.modules[module_name]
    # The loader caches the imported component in hass.data[DATA_COMPONENTS];
    # reset it so the retry re-imports instead of reusing the old module.
    hass.data[DATA_COMPONENTS].pop(DOMAIN, None)
    hass.data[OVERRIDE_APPLIED_KEY] = target_spec

    _LOGGER.warning(
        "[kia_uvo] VERSION OVERRIDE: installed %s (was %s); reloading integration",
        target_spec,
        installed,
    )
    raise ConfigEntryNotReady(f"Library override installed ({target_spec}); reloading")


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hyundai / Kia Connect from a config entry."""
    await _async_install_library_override(hass, config_entry)
    coordinator = HyundaiKiaConnectDataUpdateCoordinator(hass, config_entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed as AuthError:
        raise ConfigEntryAuthFailed(AuthError) from AuthError
    except Exception as ex:
        raise ConfigEntryNotReady(f"Config Not Ready: {ex}")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.unique_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN][config_entry.unique_id]
    if not hass.data[DOMAIN]:
        async_unload_services(hass)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    if config_entry.version == 1:
        _LOGGER.debug(f"{DOMAIN} - config data- {config_entry}")
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        pin = config_entry.data.get(CONF_PIN, DEFAULT_PIN)
        region = config_entry.data.get(CONF_REGION, "")
        brand = config_entry.data.get(CONF_BRAND, "")
        geolocation_enable = config_entry.data.get(CONF_ENABLE_GEOLOCATION_ENTITY, "")
        geolocation_use_email = config_entry.data.get(
            CONF_USE_EMAIL_WITH_GEOCODE_API, ""
        )
        no_force_finish_hour = config_entry.data.get(
            CONF_NO_FORCE_REFRESH_HOUR_FINISH, ""
        )
        no_force_start_hour = config_entry.data.get(
            CONF_NO_FORCE_REFRESH_HOUR_START, ""
        )
        force_refresh_interval = config_entry.data.get(CONF_FORCE_REFRESH_INTERVAL, "")
        scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, "")
        title = f"{BRANDS[brand]} {REGIONS[region]} {username}"
        unique_id = hashlib.sha256(title.encode("utf-8")).hexdigest()
        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_PIN: pin,
            CONF_REGION: region,
            CONF_BRAND: brand,
            CONF_ENABLE_GEOLOCATION_ENTITY: geolocation_enable,
            CONF_USE_EMAIL_WITH_GEOCODE_API: geolocation_use_email,
            CONF_NO_FORCE_REFRESH_HOUR_FINISH: no_force_finish_hour,
            CONF_NO_FORCE_REFRESH_HOUR_START: no_force_start_hour,
            CONF_FORCE_REFRESH_INTERVAL: force_refresh_interval,
            CONF_SCAN_INTERVAL: scan_interval,
        }
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)
        for entity in entities:
            registry.async_remove(entity.entity_id)

        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, title=title, data=new_data
        )
        config_entry.version = 2
        _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True
