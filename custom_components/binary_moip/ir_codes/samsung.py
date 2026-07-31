"""Common Samsung TV IR commands (AA59-style / 0xE0E0 address).

Codes are 32-bit Samsung protocol words. Discrete power and HDMI input codes
are widely used but model-dependent.
"""

from __future__ import annotations

# Sources: community AA59-00741A maps, Remote Central / AVS discrete lists.
COMMANDS: dict[str, int] = {
    "power": 0xE0E040BF,
    "power_on": 0xE0E09966,
    "power_off": 0xE0E019E6,
    "volume_up": 0xE0E0E01F,
    "volume_down": 0xE0E0D02F,
    "mute": 0xE0E0F00F,
    "channel_up": 0xE0E048B7,
    "channel_down": 0xE0E008F7,
    "source": 0xE0E0807F,
    "home": 0xE0E09E61,
    "menu": 0xE0E058A7,
    "info": 0xE0E0F807,
    "up": 0xE0E006F9,
    "down": 0xE0E08679,
    "left": 0xE0E0A659,
    "right": 0xE0E046B9,
    "ok": 0xE0E016E9,
    "back": 0xE0E01AE5,
    "exit": 0xE0E0B44B,
    "hdmi_1": 0xE0E09768,
    "hdmi_2": 0xE0E07D82,
    "hdmi_3": 0xE0E043BC,
    "hdmi_4": 0xE0E0A35C,
    "0": 0xE0E08877,
    "1": 0xE0E020DF,
    "2": 0xE0E0A05F,
    "3": 0xE0E0609F,
    "4": 0xE0E010EF,
    "5": 0xE0E0906F,
    "6": 0xE0E050AF,
    "7": 0xE0E030CF,
    "8": 0xE0E0B04F,
    "9": 0xE0E0708F,
}
