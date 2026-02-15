from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.api.schemas.tools import SireneNewBusinessesRequest


def test_naf_codes_normalized_and_deduped() -> None:
    payload = SireneNewBusinessesRequest(
        start_date=date(2025, 1, 1),
        naf_codes=["5610a", "56.10A", "  5610B  "],
    )
    assert payload.naf_codes == ["56.10A", "56.10B"]


def test_naf_codes_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        SireneNewBusinessesRequest(start_date=date(2025, 1, 1), naf_codes=[])


def test_naf_codes_invalid_rejected() -> None:
    with pytest.raises(ValidationError):
        SireneNewBusinessesRequest(start_date=date(2025, 1, 1), naf_codes=["invalid"])


def test_naf_codes_limit_enforced() -> None:
    with pytest.raises(ValidationError):
        SireneNewBusinessesRequest(
            start_date=date(2025, 1, 1),
            naf_codes=[f"5610{chr(65 + (i % 26))}" for i in range(30)],
        )


def test_end_date_before_start_date_rejected() -> None:
    with pytest.raises(ValidationError):
        SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=date(2025, 1, 1),
            naf_codes=["56.10A"],
        )


def test_last_treatment_dates_order_rejected() -> None:
    with pytest.raises(ValidationError):
        SireneNewBusinessesRequest(
            start_date=date(2025, 1, 1),
            naf_codes=["56.10A"],
            last_treatment_from=date(2025, 1, 20),
            last_treatment_to=date(2025, 1, 10),
        )


def test_valid_dates_pass() -> None:
    payload = SireneNewBusinessesRequest(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
        naf_codes=["56.10A"],
        last_treatment_from=date(2025, 1, 2),
        last_treatment_to=date(2025, 1, 5),
    )
    assert payload.end_date == date(2025, 1, 10)
