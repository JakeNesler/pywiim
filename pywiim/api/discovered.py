"""Read-only WiiM device-setting helpers discovered from app traffic.

These endpoints were observed on WiiM Amp Ultra firmware 5.2.829663 and are
described in ``docs/design/WIIM_DISCOVERED_APIS.md``. They are WiiM-specific and
read-only. Unsupported firmware returns ``None`` (or an empty list), never raises.

The mixin assumes the base client provides the ``_request`` coroutine. No state
is stored; every call goes to the device.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import Field, ValidationError

from ..exceptions import WiiMError
from ..models import _WiimBase
from .base import ApiResponse
from .constants import (
    API_ENDPOINT_GET_CEC_POWER_CTRL,
    API_ENDPOINT_GET_FEATURE_CAPABILITY,
    API_ENDPOINT_GET_HDMI_AUTO_SENSE_ENABLE,
    API_ENDPOINT_GET_INPUT_MODE_SUPPORT_LIST,
    API_ENDPOINT_GET_PLAY_MODE_GAIN_CONFIG,
    API_ENDPOINT_GROUP_LEADTIME,
    API_ENDPOINT_GROUP_SUBWOOFER_PAIR_INFO,
)
from .misc import _is_unsupported_discovered_payload

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------


class FeatureCapabilityItem(_WiimBase):
    """One entry from WiiM ``getFeatureCapbility``."""

    name: str


class FeatureCapability(_WiimBase):
    """Payload from WiiM ``getFeatureCapbility`` (misspelled in firmware).

    Amp Ultra 5.2.829663 reports names such as ``FEATURE_VOLUME_LIMIT``,
    ``FEATURE_AUDIO_CHANNEL``, ``FEATURE_VOLUME_BALANCE``, ``FEATURE_FADE_EFFECTS``,
    ``FEATURE_STATUS_LIGHT``, ``FEATURE_BUTTON_VOLUME_STEP`` and ``FEATURE_CEC_VOLUME_STEP``.
    """

    version: str | None = Field(None, alias="ver")
    feature: list[FeatureCapabilityItem] = Field(default_factory=list)

    @property
    def names(self) -> list[str]:
        """Feature names in device order."""
        return [item.name for item in self.feature]


class InputSoundCardInfo(_WiimBase):
    """Nested sound-card details from ``getInputModeSupportList``."""

    card_name: str | None = Field(None, alias="cardName")
    dev_name: str | None = Field(None, alias="devName")
    card_id: str | None = Field(None, alias="cardId")
    block_mode_access: int | None = Field(None, alias="blockModeAccess")
    auto_sense_switch: int | None = Field(None, alias="autoSenseSwitch")
    # Firmware spells this "dafaultAutosenseEnable"; keep the alias so it parses.
    default_auto_sense_enable: int | None = Field(None, alias="dafaultAutosenseEnable")
    auto_change_play_status: int | None = Field(None, alias="autoChangePlayStatus")
    support_cec: int | None = Field(None, alias="supportCEC")
    support_dolby_audio: str | None = Field(None, alias="supportDolbyAudio")  # e.g. "5.1" on the HDMI input
    bit_depth_support_list: list[int] | None = Field(None, alias="bitDepthSupportList")
    sample_rate_support_list: list[int] | None = Field(None, alias="sampleRateSupportList")
    hifi_src_version: str | None = Field(None, alias="HiFiSRCVersion")


class InputModeSupport(_WiimBase):
    """One entry from WiiM ``getInputModeSupportList``.

    Unlike ``getAudioInputCapbility`` this carries per-input hardware metadata:
    signal type, auto-sense flags, CEC support and Dolby decoding support.
    """

    index: int | None = None
    mode: str
    signal_type: str | None = Field(None, alias="signalType")
    sound_card: InputSoundCardInfo | None = Field(None, alias="soundCard")


class PlayModeGain(_WiimBase):
    """Per-input gain entry from ``getPlayModeGainConfig``."""

    mode: int | None = None  # play-mode number, e.g. 49 for HDMI
    name: str
    gain: float | None = None  # dB


class PlayModeGainConfig(_WiimBase):
    """Payload from WiiM ``getPlayModeGainConfig`` ("Input gain" in the WiiM Home app)."""

    enable: bool = False
    max_gain: float | None = None
    min_gain: float | None = None
    config: list[PlayModeGain] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _parse_plain_flag(resp: ApiResponse) -> bool | None:
    """Parse a plain ``0`` / ``1`` body. ``json.loads`` turns it into an int first."""
    parsed = resp.parsed
    if isinstance(parsed, bool):
        return parsed
    if isinstance(parsed, int) and parsed in (0, 1):
        return parsed == 1
    text = (resp.raw or "").strip()
    if text in ("0", "1"):
        return text == "1"
    return None


# ----------------------------------------------------------------------------
# Mixin
# ----------------------------------------------------------------------------


class DiscoveredAPI:
    """Read-only WiiM device-setting helpers observed on Amp Ultra firmware."""

    async def get_feature_capability(self) -> FeatureCapability | None:
        """Return the WiiM feature list from ``getFeatureCapbility``, or None if unsupported."""
        try:
            result = await self._request(API_ENDPOINT_GET_FEATURE_CAPABILITY)  # type: ignore[attr-defined]
            if isinstance(result.parsed, dict) and not _is_unsupported_discovered_payload(result.parsed):
                return FeatureCapability.model_validate(result.parsed)
        except (ValidationError, WiiMError):
            return None
        return None

    async def get_input_mode_support_list(self) -> list[InputModeSupport]:
        """Return per-input hardware metadata from ``getInputModeSupportList``.

        The HDMI entry reports ``supportDolbyAudio`` (``"5.1"`` on Amp Ultra) and
        ``supportCEC``. Returns an empty list when unsupported.
        """
        try:
            result = await self._request(API_ENDPOINT_GET_INPUT_MODE_SUPPORT_LIST)  # type: ignore[attr-defined]
        except WiiMError:
            return []
        if not isinstance(result.parsed, list):
            return []
        entries: list[InputModeSupport] = []
        for item in result.parsed:
            if not isinstance(item, dict):
                continue
            try:
                entries.append(InputModeSupport.model_validate(item))
            except ValidationError as err:
                _LOGGER.debug("getInputModeSupportList: skipping entry %s: %s", item, err)
        return entries

    async def get_hdmi_auto_sense_enabled(self) -> bool | None:
        """Return whether HDMI ARC auto-sense is on (``getHDMIAutoSenseEnable``), or None."""
        try:
            return _parse_plain_flag(await self._request(API_ENDPOINT_GET_HDMI_AUTO_SENSE_ENABLE))  # type: ignore[attr-defined]
        except WiiMError:
            return None

    async def get_cec_power_control_enabled(self) -> bool | None:
        """Return whether HDMI CEC power control is on (``getCecPowerCtrl``), or None."""
        try:
            return _parse_plain_flag(await self._request(API_ENDPOINT_GET_CEC_POWER_CTRL))  # type: ignore[attr-defined]
        except WiiMError:
            return None

    async def get_play_mode_gain_config(self) -> PlayModeGainConfig | None:
        """Return the per-input gain table from ``getPlayModeGainConfig``, or None if unsupported."""
        try:
            result = await self._request(API_ENDPOINT_GET_PLAY_MODE_GAIN_CONFIG)  # type: ignore[attr-defined]
            if isinstance(result.parsed, dict) and not _is_unsupported_discovered_payload(result.parsed):
                return PlayModeGainConfig.model_validate(result.parsed)
        except (ValidationError, WiiMError):
            return None
        return None

    async def get_wireless_subwoofer_pair_info(self) -> list[dict[str, Any]] | None:
        """Return paired wireless WiiM Sub Pro entries from ``multiroom:subwooferGetPairInfo``.

        Returns an empty list when the endpoint works but no Sub Pro is paired, and
        None when unsupported. Firmware answers plain ``OK`` to unknown ``multiroom:``
        subcommands, so ``OK`` is treated as unsupported here. Entry shape is kept
        raw because only the empty list has been observed so far.
        """
        try:
            result = await self._request(API_ENDPOINT_GROUP_SUBWOOFER_PAIR_INFO)  # type: ignore[attr-defined]
        except WiiMError:
            return None
        if not isinstance(result.parsed, dict) or _is_unsupported_discovered_payload(result.parsed):
            return None
        subs = result.parsed.get("subwoofer")
        if not isinstance(subs, list):
            return None
        return [item for item in subs if isinstance(item, dict)]

    async def get_group_audio_delay_ms(self) -> int | None:
        """Return the multiroom lead time in ms (``multiroom:ConfigGet:leadtime``), or None.

        This is the "Group Audio Delay" setting in the WiiM Home app (800 ms observed
        as the default on Amp Ultra). It is read-only here.
        """
        try:
            result = await self._request(API_ENDPOINT_GROUP_LEADTIME)  # type: ignore[attr-defined]
        except WiiMError:
            return None
        if not isinstance(result.parsed, dict) or _is_unsupported_discovered_payload(result.parsed):
            return None
        if str(result.parsed.get("status", "")).strip().upper() not in ("OK", ""):
            return None
        value = result.parsed.get("leadtime")
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None
