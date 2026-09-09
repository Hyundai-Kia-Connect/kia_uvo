"""Image entities for the Surround View Monitor (SVM / Find My Car).

The SVM image is a single composite JPEG (4472x720) containing 5 segments
side-by-side, in order: FRONT, REAR, LEFT, RIGHT, TOP (bird's-eye). Segment
widths come from SVMDetails.image_sizes (verified against live captures:
cameras use image_sizes[2], TOP uses image_sizes[4]; 4*image_sizes[2] +
image_sizes[4] == image_sizes[0]). Each entity crops the composite to its
segment. The 4 camera segments are raw fisheye; TOP is the rectilinear
bird's-eye.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import HyundaiKiaConnectDataUpdateCoordinator
from .entity import HyundaiKiaConnectEntity
from .svm_dewarp import camera_fov_deg, dewarp_fisheye

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class SVMView:
    """One SVM composite segment."""

    key: str
    translation_key: str
    icon: str
    width_index: int  # index into SVMDetails.image_sizes for this segment's width


# Order matches the composite layout: FRONT(0), REAR(1), LEFT(2), RIGHT(3),
# TOP(4). Cameras (F/R/L/R) use image_sizes[2] for width; TOP (bird's-eye)
# uses image_sizes[4].
SVM_VIEWS: tuple[SVMView, ...] = (
    SVMView("front", "svm_front", "mdi:car-arrow-right", 2),
    SVMView("rear", "svm_rear", "mdi:car-arrow-left", 2),
    SVMView("left", "svm_left", "mdi:car-side", 2),
    SVMView("right", "svm_right", "mdi:car-side", 2),
    SVMView("top", "svm_top", "mdi:car-360", 4),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up image platform."""
    coordinator: HyundaiKiaConnectDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.unique_id
    ]

    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        if vehicle.supports_svm:
            # Best-effort: populate the cache so the image entities are
            # available immediately after restart instead of waiting for a
            # manual capture. get_svm_details is a cheap cached GET — it does
            # not wake the car.
            try:
                await coordinator.async_get_svm_details(vehicle_id)
            except Exception:
                _LOGGER.debug(
                    "SVM initial fetch failed for %s", vehicle_id, exc_info=True
                )
            for order, view in enumerate(SVM_VIEWS):
                entities.append(SVMImageEntity(coordinator, vehicle, view, order))

    async_add_entities(entities)


class SVMImageEntity(ImageEntity, HyundaiKiaConnectEntity):
    """One SVM camera view (a crop of the composite image)."""

    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        coordinator: HyundaiKiaConnectDataUpdateCoordinator,
        vehicle: Vehicle,
        view: SVMView,
        order: int,
    ) -> None:
        # ImageEntity.__init__ sets up the image-proxy client + access_tokens
        # (it does not call super().__init__, so call it explicitly).
        ImageEntity.__init__(self, coordinator.hass)
        HyundaiKiaConnectEntity.__init__(self, coordinator, vehicle)
        self._view = view
        self._order = order
        self._attr_translation_key = view.translation_key
        self._attr_icon = view.icon
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_svm_{view.key}"
        details = coordinator.get_cached_svm_details(vehicle.id)
        self._attr_image_last_updated = details.captured_at if details else None

    def _handle_coordinator_update(self) -> None:
        """Refresh the capture timestamp when the coordinator pushes an update."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        self._attr_image_last_updated = details.captured_at if details else None
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if a cached image is available."""
        return self.coordinator.get_cached_svm_details(self.vehicle.id) is not None

    async def async_image(self) -> bytes | None:
        """Return bytes of this view cropped from the latest SVM composite."""
        details = self.coordinator.get_cached_svm_details(self.vehicle.id)
        if details is None or not details.image_bytes or not details.image_sizes:
            return None
        sizes = details.image_sizes
        # Need composite height + this segment's width.
        if len(sizes) <= max(self._view.width_index, 1):
            return None
        height = sizes[1]
        width = sizes[self._view.width_index]
        # x offset = sum of preceding segment widths (in SVM_VIEWS order).
        x = 0
        for view in SVM_VIEWS[: self._order]:
            if len(sizes) > view.width_index:
                x += sizes[view.width_index]
        box = (x, 0, x + width, height)
        try:
            from PIL import Image  # lazy: HA ships Pillow; avoid import-time fail
        except ImportError:
            return None
        try:
            img = Image.open(BytesIO(details.image_bytes))
            cropped = img.crop(box)
        except Exception:
            _LOGGER.debug(
                "SVM image decode failed for %s", self.vehicle.id, exc_info=True
            )
            return None
        if cropped.mode != "RGB":
            cropped = cropped.convert("RGB")

        # Camera segments are raw fisheye; dewarp on user request. TOP
        # (bird's-eye, order 4) is already rectilinear — never dewarp. FOV is
        # auto-derived from the per-capture validAngleOfView calibration; any
        # failure (no numpy, missing calibration) falls back to the raw
        # fisheye crop below. The crop is passed as a PIL image so dewarp
        # samples the decoded pixels directly — no intermediate JPEG encode.
        result = cropped
        if self._order < 4 and self.coordinator.svm_dewarp_enabled(self.vehicle.id):
            fov = camera_fov_deg(details.valid_angle_of_view, self._order)
            if fov is not None:
                # Zoom in slightly so the output rectangle stays inside the
                # fisheye circle and the worst corner stretch is cropped away.
                # Factor tuned against a daylight capture: FRONT 76 -> ~59,
                # REAR 78 -> ~61, LEFT 87 -> ~68, RIGHT 81 -> ~63. Clamp keeps
                # the value sane if calibration reports an odd FOV.
                output_fov = max(50.0, min(fov * 0.78, 85.0))
                dewarped = dewarp_fisheye(cropped, fov, output_fov_deg=output_fov)
                if dewarped is not None:
                    result = dewarped
        # Single JPEG encode at max quality / 4:4:4: the car's JPEG is the
        # only lossy generation.
        buf = BytesIO()
        result.save(buf, format="JPEG", quality=100, subsampling=0)
        return buf.getvalue()
