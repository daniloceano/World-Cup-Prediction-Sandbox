"""Lightweight country-code → flag-emoji mapping.

Robust, dependency-free approach:
- Map common FIFA 3-letter codes to ISO 3166-1 alpha-2.
- Convert alpha-2 to a regional-indicator flag emoji.
- Fall back gracefully to the raw code when no mapping exists.
"""

from __future__ import annotations

# FIFA / common 3-letter codes -> ISO 3166-1 alpha-2.
# Extend freely; unknown codes just fall back to text.
FIFA_TO_ISO2: dict[str, str] = {
    "ARG": "AR", "BRA": "BR", "FRA": "FR", "ENG": "GB", "ESP": "ES",
    "GER": "DE", "POR": "PT", "NED": "NL", "BEL": "BE", "ITA": "IT",
    "CRO": "HR", "URU": "UY", "USA": "US", "MEX": "MX", "CAN": "CA",
    "JPN": "JP", "KOR": "KR", "KSA": "SA", "QAT": "QA", "IRN": "IR",
    "AUS": "AU", "MAR": "MA", "SEN": "SN", "GHA": "GH", "NGA": "NG",
    "CMR": "CM", "EGY": "EG", "TUN": "TN", "ALG": "DZ", "CIV": "CI",
    "SUI": "CH", "SRB": "RS", "POL": "PL", "DEN": "DK", "SWE": "SE",
    "NOR": "NO", "WAL": "GB", "SCO": "GB", "AUT": "AT", "CZE": "CZ",
    "UKR": "UA", "TUR": "TR", "GRE": "GR", "RUS": "RU", "COL": "CO",
    "CHI": "CL", "PER": "PE", "ECU": "EC", "PAR": "PY", "VEN": "VE",
    "BOL": "BO", "CRC": "CR", "PAN": "PA", "HON": "HN", "JAM": "JM",
    "RSA": "ZA", "NZL": "NZ", "IRQ": "IQ", "UAE": "AE", "JOR": "JO",
    "IND": "IN", "CHN": "CN", "THA": "TH", "VIE": "VN", "IDN": "ID",
}

# Three-letter ISO alpha-3 that differ from the FIFA code (best-effort).
ISO3_TO_ISO2: dict[str, str] = {
    "DEU": "DE", "NLD": "NL", "PRT": "PT", "GBR": "GB", "CHE": "CH",
    "HRV": "HR", "URY": "UY", "SAU": "SA", "KOR": "KR", "JPN": "JP",
}


def _iso2_to_emoji(iso2: str) -> str:
    """Convert a 2-letter ISO country code to a regional-indicator emoji."""
    iso2 = iso2.upper()
    if len(iso2) != 2 or not iso2.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + (ord(c) - ord("A"))) for c in iso2)


def flag_for(code: str | None) -> str:
    """Return a flag emoji for a team code, or an empty string if unknown.

    Accepts FIFA 3-letter, ISO alpha-3, or ISO alpha-2 codes.
    """
    if not code:
        return ""
    code = code.strip().upper()
    if len(code) == 2:
        return _iso2_to_emoji(code)
    iso2 = FIFA_TO_ISO2.get(code) or ISO3_TO_ISO2.get(code)
    return _iso2_to_emoji(iso2) if iso2 else ""


def label_for(code: str | None, name: str | None = None) -> str:
    """Return a display label: ``🇧🇷 Brazil`` when possible, else a sane fallback."""
    flag = flag_for(code)
    text = name or code or "?"
    return f"{flag} {text}".strip()
