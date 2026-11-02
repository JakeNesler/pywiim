# WiiM Discovered Read-Only APIs

This note records WiiM HTTP APIs discovered from app traffic and reported in
[pywiim issue #20](https://github.com/mjcumming/pywiim/issues/20). Treat these
as WiiM-specific until real-device testing proves broader LinkPlay/OEM support.

pywiim exposes these endpoints as read-only helpers first. The three input
endpoints below are now consumed as a WiiM-only overlay on source enumeration
(verified on a real WiiM device); the others remain diagnostics-only until their
payloads are tested across more devices and firmware versions.

## Endpoint Summary

| Command | pywiim helper | Model | Current use |
| --- | --- | --- | --- |
| `getAudioInputEnable` | `client.get_audio_input_enable()` | `AudioInputEnable` | Enable-filter overlay: hides user-disabled inputs from `available_sources` |
| `getAudioInputCapbility` | `client.get_audio_input_capability()` | `AudioInputCapability` | Authoritative input list: gap-fills enumeration missed by `plm_support`/`InputList` |
| `getModeRename` | `client.get_mode_rename()` | `dict[str, str]` | Custom label overlay on `source_catalog` names (stable ids preserved) |
| `GetAcousticCapability` | `client.get_acoustic_capability()` | `AcousticCapability` | Read-only acoustic capability blocks |
| `getAllRoutines` | `client.get_all_routines()` | `RoutineList` | Read-only routine list |
| `getSoundCardModeSupportList` | `client.get_sound_card_mode_support_list()` | `list[SoundCardModeSupport]` | Read-only output hardware metadata |
| `getFeatureCapbility` | `client.get_feature_capability()` | `FeatureCapability` | Read-only feature-name list |
| `getInputModeSupportList` | `client.get_input_mode_support_list()` | `list[InputModeSupport]` | Read-only per-input hardware metadata (CEC, Dolby) |
| `getHDMIAutoSenseEnable` | `client.get_hdmi_auto_sense_enabled()` | `bool \| None` | Read-only HDMI auto-sense flag |
| `getCecPowerCtrl` | `client.get_cec_power_control_enabled()` | `bool \| None` | Read-only HDMI CEC power-control flag |
| `getPlayModeGainConfig` | `client.get_play_mode_gain_config()` | `PlayModeGainConfig` | Read-only per-input gain table |
| `multiroom:subwooferGetPairInfo` | `client.get_wireless_subwoofer_pair_info()` | `list[dict] \| None` | Read-only wireless Sub Pro pairing list |
| `multiroom:ConfigGet:leadtime` | `client.get_group_audio_delay_ms()` | `int \| None` | Read-only Group Audio Delay (ms) |

Unsupported endpoints, plain `Failed`, `unknown command`, non-JSON bodies, and
transport errors should not make discovery fail. Helpers return `None` or an
empty list, depending on the natural shape of the API.

## `getAudioInputEnable`

Example shape:

```json
{
  "ver": "1.0",
  "audioInput": [
    {"mode": "wifi", "enable": 1},
    {"mode": "bluetooth", "enable": 1},
    {"mode": "line-in", "enable": 1},
    {"mode": "optical", "enable": 1},
    {"mode": "HDMI", "enable": 1},
    {"mode": "phono", "enable": 1}
  ]
}
```

Implemented: overlaid on stable source ids at connect (`wiim_input_enable` in
`capabilities`). `available_sources` drops inputs with `enable=0`, except the
currently active source, which stays visible for correct state display.

## `getAudioInputCapbility`

The firmware command is misspelled as `Capbility`. It returns available input
modes without the enable/disable state from `getAudioInputEnable`.

Example shape:

```json
{
  "ver": "1.0",
  "audioInput": [
    {"mode": "wifi"},
    {"mode": "line-in"},
    {"mode": "bluetooth"},
    {"mode": "optical"}
  ]
}
```

Implemented: gap-fills `available_sources` with authoritative physical inputs
that `plm_support`/`InputList` enumeration missed (`wiim_input_capability` in
`capabilities`). Modes are normalized through `canonical_source_key()` and deduped
by canonical id before use.

## `getModeRename`

Example shape:

```json
{
  "phono": "unused phono",
  "SPDIF-In": "Phono",
  "optical": "Phono"
}
```

Firmware may return plain `Failed` when no input has been renamed.

Implemented: overlaid as the display `name` on `source_catalog` entries and in
`available_sources` (`source_rename` in `capabilities`). Stable ids are never
changed — if the user names Optical "Phono", the id stays `optical`. `set_source()`
resolves the custom label back to the canonical id. When firmware points several
mode keys at one label (e.g. `optical` and `SPDIF-In` → "Optical Mike"), the
canonical hardware id wins (`source_rename_reverse()`).

## `GetAcousticCapability`

Example shape:

```json
{
  "Version": "1.0",
  "GEQ": {"Version": "1.0"},
  "PEQ": {"Version": "1.0", "Filters": ["OFF", "LS", "PK", "HS", "LP", "HP"]},
  "RC": {"Version": "1.0"},
  "HeadphoneEQ": {"Version": "1.0"},
  "SubLPF": {"Version": "1.0"},
  "Evaluation": {"Version": "1.1"},
  "EQBlock": {"Version": "1.0", "Blocks": [{"id": 1, "type": "EQ"}]},
  "OutputDelay": {
    "Version": "1.0",
    "PerOutputDelay": false,
    "EnableMicroDelay": true,
    "MinDelayUs": -1000000,
    "MaxDelayUs": 1000000,
    "StepDelayUs": 100
  }
}
```

Current model keeps capability blocks as dictionaries. This avoids committing
too early to HA controls or high-level pywiim feature flags for GEQ, PEQ, room
correction, headphone EQ, output delay, or evaluation APIs.

## `getAllRoutines`

Example shape:

```json
{
  "routines": [
    {
      "id": "0000000067570795",
      "name": "PC",
      "index": 3,
      "createDate": "2026-06-23T06:08:26Z",
      "updateDate": "2026-06-23T06:08:56Z",
      "steps": [
        {"type": "audioInput", "payload": {"input": "optical"}},
        {"type": "audioOutput", "payload": {"output": ""}},
        {"type": "loopMode", "payload": {"mode": 4}},
        {"type": "subwoofer", "payload": {"subOutput": 1}}
      ]
    }
  ]
}
```

Routines are not playback presets. They are device-side action sequences.
pywiim exposes read-only routine metadata only; execution and mutation endpoints
are not known yet.

## `getSoundCardModeSupportList`

Example shape:

```json
[
  {
    "index": 5,
    "mode": "AUDIO_OUTPUT_UAC_CARD_MODE",
    "soundCard": {
      "cardName": "SABRE-D70 Pro SABRE",
      "devName": "Topping D70 Pro SABRE at usb-xhci-hcd.0.auto-1.2, high speed",
      "cardId": "hw:1,0",
      "channelMax": 2,
      "bitDepthMax": 32,
      "sampleRateMax": 192000,
      "sampleRateSupportList": [44100, 48000, 88200, 96000, 176400, 192000],
      "HiFiSRCVersion": "1.1"
    }
  }
]
```

Field note: `index` does not appear to match the older output mode integer used
for reads or writes. Treat `mode` as identity and `index` as display/debug
metadata only.

WiiM Sound Lite (`WiiM_Sound_Lite_V2`, wiim #270) returns a single speaker
row (`AUDIO_OUTPUT_SPEAKER_MODE`, `devName: "Speaker Out"`). That list does
**not** include Bluetooth Out and does **not** change when the app is on
Bluetooth Out. Current output still comes from `getNewAudioOutputHardwareMode`
(`hardware` + `source`). This endpoint can later gap-fill Speaker Out for
unknown speaker models; it is not a complete output-mode catalog.

Possible later use: enrich audio-output availability, especially USB DAC
presence and capability metadata. Do not replace the existing output probe
strategy until this endpoint is tested on multiple WiiM models and firmware
versions.

## Device-setting endpoints observed on WiiM Amp Ultra (2026-11)

All payloads below come from a WiiM Amp Ultra on firmware `Linkplay.5.2.829663`.
They are read-only in pywiim; the matching `set*` commands exist in the community
OpenAPI spec but are not exposed until their behaviour is verified.

### `getFeatureCapbility`

Misspelled in firmware, like `getAudioInputCapbility`.

```json
{
  "ver": "1.0",
  "feature": [
    {"name": "FEATURE_VOLUME_LIMIT"},
    {"name": "FEATURE_AUDIO_CHANNEL"},
    {"name": "FEATURE_VOLUME_BALANCE"},
    {"name": "FEATURE_FADE_EFFECTS"},
    {"name": "FEATURE_STATUS_LIGHT"},
    {"name": "FEATURE_BUTTON_VOLUME_STEP"},
    {"name": "FEATURE_CEC_VOLUME_STEP"}
  ]
}
```

No Home Theater or surround feature name appears in this list on the firmware tested.

### `getInputModeSupportList`

Per-input hardware metadata. The HDMI entry is the only one that reports
`supportCEC` and `supportDolbyAudio`. Note the firmware typo `dafaultAutosenseEnable`.

```json
[
  {"index": 1, "mode": "line-in", "signalType": "I2S",
   "soundCard": {"cardName": "AMLAUGESOUND", "devName": "Line In", "cardId": "hw:0,2",
                 "blockModeAccess": 1, "autoSenseSwitch": 1, "dafaultAutosenseEnable": 0,
                 "autoChangePlayStatus": 1, "bitDepthSupportList": [16, 24, 32],
                 "sampleRateSupportList": [44100, 48000, 88200, 96000, 176400, 192000],
                 "HiFiSRCVersion": "1.0"}},
  {"index": 2, "mode": "optical", "signalType": "SPDIF",
   "soundCard": {"cardName": "AMLAUGESOUND", "devName": "Optical In", "cardId": "hw:0,4",
                 "blockModeAccess": 0, "autoSenseSwitch": 1, "dafaultAutosenseEnable": 0,
                 "autoChangePlayStatus": 1, "bitDepthSupportList": [16, 24, 32],
                 "sampleRateSupportList": [44100, 48000, 88200, 96000, 176400, 192000]}},
  {"index": 3, "mode": "HDMI", "signalType": "SPDIF",
   "soundCard": {"cardName": "AMLAUGESOUND", "devName": "TV", "cardId": "hw:0,4",
                 "blockModeAccess": 0, "autoSenseSwitch": 1, "dafaultAutosenseEnable": 1,
                 "autoChangePlayStatus": 1, "supportCEC": 1, "supportDolbyAudio": "5.1"}}
]
```

### `getHDMIAutoSenseEnable` and `getCecPowerCtrl`

Plain `0` / `1` bodies (both `1` on the device tested). `getAutoSenseEnable` and
`getSpdifAutoSenseEnable` exist as well and returned `0`; they are not wrapped yet.

### `getPlayModeGainConfig`

The "Input gain" table from the app. Gains are strings in dB.

```json
{
  "enable": 0,
  "max_gain": "10.0",
  "min_gain": "-10.0",
  "config": [
    {"mode": 10, "name": "wifi", "gain": "0.0"},
    {"mode": 40, "name": "line-in", "gain": "0.0"},
    {"mode": 41, "name": "bluetooth", "gain": "0.0"},
    {"mode": 43, "name": "optical", "gain": "0.0"},
    {"mode": 49, "name": "HDMI", "gain": "0.0"}
  ]
}
```

### `multiroom:subwooferGetPairInfo`

Wireless WiiM Sub Pro pairing list. Only the empty form has been observed:

```json
{ "subwoofer": [ ] }
```

`multiroom:subwooferPair:<...>` and `multiroom:subwooferForget:{"uuid":"..."}`
exist in the community spec; pywiim does not send them. Caution: firmware answers
plain `OK` to any unknown `multiroom:` subcommand, so `OK` is not evidence that a
guessed command exists. pywiim treats `OK` here as unsupported.

### `multiroom:ConfigGet:leadtime`

```json
{"status": "OK", "leadtime": "800"}
```

This is the "Group Audio Delay" setting from the app (800 ms default). The
`multiroom:ConfigGet:realtime_cache_limit` sibling returned the same value.

### Also observed, not wrapped

`getPowerModeTime` (standby / sleep intervals), `get_ui_config` (display layout
per input), `getHwErrorInfo` (hardware self-test), `GetSyncPlayExtraDelay`
(`{"SyncPlayExtraDelay": 0.000}`), `getSpdifInNoiseRemove`, and
`getMainSubExtraDelay`, which returned an `errorType -1000` body while the
subwoofer output was disabled. `GetAcousticCapability` on this firmware adds
`RC.LevelMatch`, `EQHeadroom` (`Off` / `Auto` / `Manual`) and `MainProtect` blocks.

## Related daily-use APIs

The same app-string sweep exposed a few endpoints that are closer to daily
listening than one-time setup:

| Command | pywiim helper | Model | Current use |
| --- | --- | --- | --- |
| `EQGetLV2Band:http://moddevices.com/plugins/caps/Eq10HP` | `client.get_graphic_eq_bands()` | `GraphicEQSettings` | Read-only graphic EQ state |
| `EQGetLV2SourceBandEx:{...Eq10HP...}` | `client.get_graphic_eq_bands(source_name=...)` | `GraphicEQSettings` | Read-only per-source graphic EQ state |
| `EQv2GetList:http://moddevices.com/plugins/caps/Eq10HP` | `client.get_graphic_eq_preset_list()` | `dict[str, list[str]]` | Read-only graphic EQ preset names |
| `EQGetLV2SourceBandEx` at EQLevel 2 | `client.get_room_correction()` | `RoomCorrectionSettings` | RoomFit on/off and active profile |
| `EQv2GetNewList` at EQLevel 2 | `client.get_room_correction_profiles()` | `list[str]` | Saved RoomFit profile names |
| `EQv2SourceLoad` / `EQSourceOff` at EQLevel 2 | `client.set_room_correction(name)` | none | Load a RoomFit profile, or turn it off |

Write commands for graphic EQ are intentionally not exposed yet. Use the WiiM
app for graphic EQ setup until write behavior is validated across more models
and firmware versions. RoomFit profile create and edit stay in the WiiM app.

## Intentionally Not Exposed

One-off setup, account, network, update-server, token, static-IP, Wi-Fi, Alexa,
and factory-reset style commands from the app bundle are not good Home
Assistant surfaces. pywiim may keep selected read-only diagnostics over time,
but user-facing HA entities/services should focus on daily listening and
automation workflows.

## Real-Device Testing

Use the diagnostics CLI for a focused JSON report:

```bash
python -m pywiim.cli.diagnostics 192.168.1.100 --discovered-apis-only --output discovered-apis.json
```

Use `docs/testing/CURL_HTTPAPI.md` when raw HTTP payloads are needed. For each
endpoint, record:

- device model and firmware
- protocol/port used
- endpoint response when supported
- exact unsupported response when not supported
- whether the WiiM app setting changes the payload predictably

Once we have enough data, decide separately whether to wire these into:

- `source_catalog` metadata
- audio-output support lists
- capability flags
- diagnostics
- Home Assistant integration behavior

### Observed Devices

| Date | Device | Firmware | Supported discovered endpoints | Notes |
| --- | --- | --- | --- | --- |
| 2026-06-27 | Cabin Speakers (`WiiM_Pro_with_gc4a`) | `Linkplay.4.8.814756` | `getAudioInputEnable`, `GetAcousticCapability`, `getAllRoutines` | `getModeRename` returned empty/unsupported; `getSoundCardModeSupportList` returned empty. Inputs reported: `wifi`, `bluetooth`, `line-in`, `optical`. |
| 2026-06-27 | Main Deck (`ARYLIC_H50`) | `Linkplay.4.6.529755` | None | Optional endpoints returned firmware error payloads such as `unknown command` / `Fail`; helpers classify these as unsupported. |
| 2026-06-27 | Dock Speakers (`UP2STREAM_AMP_V4`) | `4.6.415145` | None | All five helpers returned unsupported/empty. |
| 2026-11-01 | WiiM Amp Ultra (`WiiM_Amp_Ultra`) | `Linkplay.5.2.829663` | `getAudioInputEnable`, `getAudioInputCapbility`, `GetAcousticCapability`, `getSoundCardModeSupportList`, `getFeatureCapbility`, `getInputModeSupportList`, `getHDMIAutoSenseEnable`, `getCecPowerCtrl`, `getPlayModeGainConfig`, `multiroom:subwooferGetPairInfo`, `multiroom:ConfigGet:leadtime` | HTTPS/443. `getModeRename` returned `Failed` (nothing renamed); `getAllRoutines` returned `{}`; sound-card list is a single `AUDIO_OUTPUT_SPEAKER_MODE` row. Inputs: `wifi`, `line-in`, `bluetooth`, `optical`, `HDMI`, `udisk`. |
