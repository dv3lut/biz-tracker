"""Helper utilities for building external URLs."""
from __future__ import annotations

from typing import Final

ANNULAIRE_ETABLISSEMENT_BASE_URL: Final[str] = "https://annuaire-entreprises.data.gouv.fr/etablissement"


def build_annuaire_etablissement_url(siret: str | None) -> str | None:
    """Return the public annuaire URL for a given SIRET, or ``None`` if invalid."""
    if not siret:
        return None
    normalized = "".join(ch for ch in siret if ch.isdigit())
    if len(normalized) != 14:
        return None
    return f"{ANNULAIRE_ETABLISSEMENT_BASE_URL}/{normalized}"
