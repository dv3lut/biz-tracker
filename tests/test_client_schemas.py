from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.api.schemas.clients import ClientCreate, ClientUpdate


def test_client_create_requires_listing_status():
    with pytest.raises(ValidationError):
        ClientCreate(name="Test", start_date=date(2024, 1, 1), listing_statuses=[], recipients=[])


def test_client_update_validates_listing_statuses():
    with pytest.raises(ValidationError):
        ClientUpdate(listing_statuses=[])

    payload = ClientUpdate(listing_statuses=None)
    assert payload.listing_statuses is None
