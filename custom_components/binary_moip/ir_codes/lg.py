"""Common LG TV IR commands (NEC protocol, 0x20DF address family).

Codes are 32-bit NEC words as commonly published for LG TVs. Discrete power
and HDMI input codes are widely used but model-dependent.
"""

from __future__ import annotations

# Sources: community NEC maps used with Broadlink / universal remotes.
COMMANDS: dict[str, int] = {
    "power": 0x20DF10EF,
    "power_on": 0x20DF23DC,
    "power_off": 0x20DFA35C,
    "volume_up": 0x20DF40BF,
    "volume_down": 0x20DFC03F,
    "mute": 0x20DF906F,
    "channel_up": 0x20DF00FF,
    "channel_down": 0x20DF807F,
    "source": 0x20DFD02F,
    "home": 0x20DF3EC1,
    "menu": 0x20DFC23D,
    "info": 0x20DF55AA,
    "up": 0x20DF02FD,
    "down": 0x20DF827D,
    "left": 0x20DFE01F,
    "right": 0x20DF609F,
    "ok": 0x20DF22DD,
    "back": 0x20DF14EB,
    "exit": 0x20DFDA25,
    "hdmi_1": 0x20DF738C,
    "hdmi_2": 0x20DF33CC,
    "hdmi_3": 0x20DF9768,
    "hdmi_4": 0x20DF5BA4,
    "0": 0x20DF08F7,
    "1": 0x20DF8877,
    "2": 0x20DF48B7,
    "3": 0x20DFC837,
    "4": 0x20DF28D7,
    "5": 0x20DFA857,
    "6": 0x20DF6897,
    "7": 0x20DFE817,
    "8": 0x20DF18E7,
    "9": 0x20DF9867,
}
