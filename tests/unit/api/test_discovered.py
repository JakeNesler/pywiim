"""Unit tests for the DiscoveredAPI mixin (read-only WiiM device-setting helpers)."""

from __future__ import annotations

import pytest

from pywiim.api.base import ApiResponse
from pywiim.api.constants import (
    API_ENDPOINT_GET_CEC_POWER_CTRL,
    API_ENDPOINT_GET_FEATURE_CAPABILITY,
    API_ENDPOINT_GET_HDMI_AUTO_SENSE_ENABLE,
    API_ENDPOINT_GET_INPUT_MODE_SUPPORT_LIST,
    API_ENDPOINT_GET_PLAY_MODE_GAIN_CONFIG,
    API_ENDPOINT_GROUP_LEADTIME,
    API_ENDPOINT_GROUP_SUBWOOFER_PAIR_INFO,
)
from pywiim.api.discovered import DiscoveredAPI
from pywiim.exceptions import WiiMRequestError

UNSUPPORTED = ApiResponse(parsed={"error": "unsupported_command", "raw": "unknown command"}, raw=None)
UNKNOWN_TEXT = ApiResponse(parsed=None, raw="unknown command")

# Payloads captured from a WiiM Amp Ultra on firmware 5.2.829663 (2026-11-01).
FEATURE_PAYLOAD = {
    "ver": "1.0",
    "feature": [
        {"name": "FEATURE_VOLUME_LIMIT"},
        {"name": "FEATURE_AUDIO_CHANNEL"},
        {"name": "FEATURE_CEC_VOLUME_STEP"},
    ],
}
INPUT_MODE_PAYLOAD = [
    {
        "index": 1,
        "mode": "line-in",
        "signalType": "I2S",
        "soundCard": {
            "cardName": "AMLAUGESOUND",
            "devName": "Line In",
            "cardId": "hw:0,2",
            "blockModeAccess": 1,
            "autoSenseSwitch": 1,
            "dafaultAutosenseEnable": 0,
            "autoChangePlayStatus": 1,
            "bitDepthSupportList": [16, 24, 32],
            "sampleRateSupportList": [44100, 48000, 96000, 192000],
            "HiFiSRCVersion": "1.0",
        },
    },
    {
        "index": 3,
        "mode": "HDMI",
        "signalType": "SPDIF",
        "soundCard": {
            "cardName": "AMLAUGESOUND",
            "devName": "TV",
            "cardId": "hw:0,4",
            "autoSenseSwitch": 1,
            "dafaultAutosenseEnable": 1,
            "supportCEC": 1,
            "supportDolbyAudio": "5.1",
        },
    },
]
GAIN_PAYLOAD = {
    "enable": 0,
    "max_gain": "10.0",
    "min_gain": "-10.0",
    "config": [
        {"mode": 10, "name": "wifi", "gain": "0.0"},
        {"mode": 49, "name": "HDMI", "gain": "-2.5"},
    ],
}


def _client(response: ApiResponse | Exception, seen: list[str] | None = None) -> DiscoveredAPI:
    class TestClient(DiscoveredAPI):
        async def _request(self, endpoint):
            if seen is not None:
                seen.append(endpoint)
            if isinstance(response, Exception):
                raise response
            return response

    return TestClient()


class TestFeatureCapability:
    @pytest.mark.asyncio
    async def test_parses_feature_names(self):
        seen: list[str] = []
        result = await _client(ApiResponse(parsed=FEATURE_PAYLOAD, raw=None), seen).get_feature_capability()

        assert seen == [API_ENDPOINT_GET_FEATURE_CAPABILITY]
        assert result is not None
        assert result.version == "1.0"
        assert result.names == ["FEATURE_VOLUME_LIMIT", "FEATURE_AUDIO_CHANNEL", "FEATURE_CEC_VOLUME_STEP"]

    @pytest.mark.asyncio
    async def test_unsupported_returns_none(self):
        assert await _client(UNSUPPORTED).get_feature_capability() is None
        assert await _client(UNKNOWN_TEXT).get_feature_capability() is None

    @pytest.mark.asyncio
    async def test_request_error_returns_none(self):
        assert await _client(WiiMRequestError("boom")).get_feature_capability() is None


class TestInputModeSupportList:
    @pytest.mark.asyncio
    async def test_parses_entries_including_firmware_typo_alias(self):
        seen: list[str] = []
        result = await _client(ApiResponse(parsed=INPUT_MODE_PAYLOAD, raw=None), seen).get_input_mode_support_list()

        assert seen == [API_ENDPOINT_GET_INPUT_MODE_SUPPORT_LIST]
        assert [entry.mode for entry in result] == ["line-in", "HDMI"]
        line_in, hdmi = result
        assert line_in.signal_type == "I2S"
        assert line_in.sound_card is not None
        assert line_in.sound_card.default_auto_sense_enable == 0
        assert line_in.sound_card.sample_rate_support_list == [44100, 48000, 96000, 192000]
        assert hdmi.sound_card is not None
        assert hdmi.sound_card.dev_name == "TV"
        assert hdmi.sound_card.support_cec == 1
        assert hdmi.sound_card.support_dolby_audio == "5.1"

    @pytest.mark.asyncio
    async def test_skips_malformed_entries(self):
        payload = [{"index": 1}, "junk", {"mode": "optical"}]
        result = await _client(ApiResponse(parsed=payload, raw=None)).get_input_mode_support_list()

        assert [entry.mode for entry in result] == ["optical"]

    @pytest.mark.asyncio
    async def test_non_list_or_error_returns_empty(self):
        assert await _client(UNSUPPORTED).get_input_mode_support_list() == []
        assert await _client(UNKNOWN_TEXT).get_input_mode_support_list() == []
        assert await _client(WiiMRequestError("boom")).get_input_mode_support_list() == []


class TestPlainFlags:
    @pytest.mark.asyncio
    async def test_hdmi_auto_sense_json_int(self):
        seen: list[str] = []
        assert await _client(ApiResponse(parsed=1, raw=None), seen).get_hdmi_auto_sense_enabled() is True
        assert seen == [API_ENDPOINT_GET_HDMI_AUTO_SENSE_ENABLE]
        assert await _client(ApiResponse(parsed=0, raw=None)).get_hdmi_auto_sense_enabled() is False

    @pytest.mark.asyncio
    async def test_hdmi_auto_sense_raw_text_and_unknown(self):
        assert await _client(ApiResponse(parsed=None, raw="1")).get_hdmi_auto_sense_enabled() is True
        assert await _client(UNKNOWN_TEXT).get_hdmi_auto_sense_enabled() is None
        assert await _client(ApiResponse(parsed=None, raw="OK")).get_hdmi_auto_sense_enabled() is None
        assert await _client(WiiMRequestError("boom")).get_hdmi_auto_sense_enabled() is None

    @pytest.mark.asyncio
    async def test_cec_power_control(self):
        seen: list[str] = []
        assert await _client(ApiResponse(parsed=1, raw=None), seen).get_cec_power_control_enabled() is True
        assert seen == [API_ENDPOINT_GET_CEC_POWER_CTRL]
        assert await _client(ApiResponse(parsed=None, raw="0")).get_cec_power_control_enabled() is False
        assert await _client(UNKNOWN_TEXT).get_cec_power_control_enabled() is None


class TestPlayModeGainConfig:
    @pytest.mark.asyncio
    async def test_parses_gain_table(self):
        seen: list[str] = []
        result = await _client(ApiResponse(parsed=GAIN_PAYLOAD, raw=None), seen).get_play_mode_gain_config()

        assert seen == [API_ENDPOINT_GET_PLAY_MODE_GAIN_CONFIG]
        assert result is not None
        assert result.enable is False
        assert result.max_gain == 10.0
        assert result.min_gain == -10.0
        assert [(entry.mode, entry.name, entry.gain) for entry in result.config] == [
            (10, "wifi", 0.0),
            (49, "HDMI", -2.5),
        ]

    @pytest.mark.asyncio
    async def test_unsupported_returns_none(self):
        assert await _client(UNSUPPORTED).get_play_mode_gain_config() is None
        assert await _client(UNKNOWN_TEXT).get_play_mode_gain_config() is None
        assert await _client(WiiMRequestError("boom")).get_play_mode_gain_config() is None


class TestWirelessSubwooferPairInfo:
    @pytest.mark.asyncio
    async def test_empty_pairing_list(self):
        seen: list[str] = []
        result = await _client(ApiResponse(parsed={"subwoofer": []}, raw=None), seen).get_wireless_subwoofer_pair_info()

        assert seen == [API_ENDPOINT_GROUP_SUBWOOFER_PAIR_INFO]
        assert result == []

    @pytest.mark.asyncio
    async def test_paired_entries_kept_raw(self):
        payload = {"subwoofer": [{"uuid": "FF98F824AAAA", "name": "Sub Pro"}, "junk"]}
        result = await _client(ApiResponse(parsed=payload, raw=None)).get_wireless_subwoofer_pair_info()

        assert result == [{"uuid": "FF98F824AAAA", "name": "Sub Pro"}]

    @pytest.mark.asyncio
    async def test_plain_ok_and_errors_are_unsupported(self):
        # Unknown multiroom: subcommands answer plain OK, which must not count as support.
        assert await _client(ApiResponse(parsed=None, raw="OK")).get_wireless_subwoofer_pair_info() is None
        assert await _client(UNKNOWN_TEXT).get_wireless_subwoofer_pair_info() is None
        assert await _client(UNSUPPORTED).get_wireless_subwoofer_pair_info() is None
        assert await _client(WiiMRequestError("boom")).get_wireless_subwoofer_pair_info() is None


class TestGroupAudioDelay:
    @pytest.mark.asyncio
    async def test_parses_leadtime(self):
        seen: list[str] = []
        payload = {"status": "OK", "leadtime": "800"}
        assert await _client(ApiResponse(parsed=payload, raw=None), seen).get_group_audio_delay_ms() == 800
        assert seen == [API_ENDPOINT_GROUP_LEADTIME]

    @pytest.mark.asyncio
    async def test_failed_or_unsupported_returns_none(self):
        assert await _client(ApiResponse(parsed={"status": "Failed"}, raw=None)).get_group_audio_delay_ms() is None
        assert await _client(ApiResponse(parsed={"status": "OK"}, raw=None)).get_group_audio_delay_ms() is None
        assert await _client(ApiResponse(parsed=None, raw="OK")).get_group_audio_delay_ms() is None
        assert await _client(UNKNOWN_TEXT).get_group_audio_delay_ms() is None
        assert await _client(WiiMRequestError("boom")).get_group_audio_delay_ms() is None


def test_client_exposes_discovered_helpers():
    from pywiim import FeatureCapability, InputModeSupport, PlayModeGainConfig, WiiMClient

    for name in (
        "get_feature_capability",
        "get_input_mode_support_list",
        "get_hdmi_auto_sense_enabled",
        "get_cec_power_control_enabled",
        "get_play_mode_gain_config",
        "get_wireless_subwoofer_pair_info",
        "get_group_audio_delay_ms",
    ):
        assert callable(getattr(WiiMClient, name))
    assert FeatureCapability and InputModeSupport and PlayModeGainConfig
