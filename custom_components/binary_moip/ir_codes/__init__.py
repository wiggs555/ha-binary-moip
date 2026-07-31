"""Built-in Pronto IR maps for common TV brands."""

from __future__ import annotations

from . import lg, samsung
from .pronto import encode_nec, encode_samsung

BRAND_SAMSUNG = "samsung"
BRAND_LG = "lg"

SUPPORTED_BRANDS = (BRAND_SAMSUNG, BRAND_LG)

_ENCODERS = {
    BRAND_SAMSUNG: (samsung.COMMANDS, encode_samsung),
    BRAND_LG: (lg.COMMANDS, encode_nec),
}


def list_commands(brand: str) -> list[str]:
    """Return sorted command names for a brand."""
    key = brand.strip().lower()
    if key not in _ENCODERS:
        raise ValueError(f"Unsupported IR brand: {brand}")
    commands, _ = _ENCODERS[key]
    return sorted(commands)


def resolve_pronto(brand: str, command: str) -> str:
    """Resolve a brand + command name to Pronto hex.

    Raises:
        ValueError: If the brand or command is unknown.
    """
    brand_key = brand.strip().lower()
    if brand_key not in _ENCODERS:
        supported = ", ".join(SUPPORTED_BRANDS)
        raise ValueError(f"Unsupported IR brand '{brand}'. Expected one of: {supported}")

    command_key = command.strip().lower()
    commands, encoder = _ENCODERS[brand_key]
    code = commands.get(command_key)
    if code is None:
        known = ", ".join(sorted(commands))
        raise ValueError(
            f"Unknown IR command '{command}' for brand '{brand_key}'. "
            f"Known commands: {known}"
        )
    return encoder(code)
