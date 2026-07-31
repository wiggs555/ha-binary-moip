"""Encode Samsung and NEC IR command words as Pronto hex."""

from __future__ import annotations

# Pronto frequency timebase (µs). freq_code ≈ 1e6 / (Hz * this).
_PRONTO_PERIOD_US = 0.241246
_DEFAULT_HZ = 38_000
_UNIT_US = 564.0
_GAP_US = 44_000.0


def _freq_code(hz: float = _DEFAULT_HZ) -> int:
    return round(1_000_000 / (hz * _PRONTO_PERIOD_US))


def _us_to_ticks(us: float, freq_code: int) -> int:
    return max(1, round(us / (freq_code * _PRONTO_PERIOD_US)))


def _bursts_to_pronto(bursts_us: list[float], hz: float = _DEFAULT_HZ) -> str:
    """Build a Pronto hex string from mark/space durations in microseconds."""
    freq = _freq_code(hz)
    ticks = [_us_to_ticks(us, freq) for us in bursts_us]
    n_pairs = len(ticks) // 2
    # Learned-style layout used by many Pronto databases: once=0, repeat=n.
    words = [0, freq, 0, n_pairs, *ticks]
    return " ".join(f"{word:04X}" for word in words)


def encode_samsung(code: int) -> str:
    """Encode a 32-bit Samsung IR word (e.g. 0xE0E040BF) as Pronto hex."""
    bursts: list[float] = [8 * _UNIT_US, 8 * _UNIT_US]
    for i in range(31, -1, -1):
        bit = (code >> i) & 1
        bursts.append(_UNIT_US)
        bursts.append((3 if bit else 1) * _UNIT_US)
    bursts.extend([_UNIT_US, _GAP_US])
    return _bursts_to_pronto(bursts)


def encode_nec(code: int) -> str:
    """Encode a 32-bit NEC IR word (e.g. 0x20DF10EF) as Pronto hex."""
    bursts: list[float] = [16 * _UNIT_US, 8 * _UNIT_US]
    for i in range(31, -1, -1):
        bit = (code >> i) & 1
        bursts.append(_UNIT_US)
        bursts.append((3 if bit else 1) * _UNIT_US)
    bursts.extend([_UNIT_US, _GAP_US])
    return _bursts_to_pronto(bursts)
