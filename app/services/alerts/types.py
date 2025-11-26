from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.db import models
from app.services.client_service import ClientEmailPayload


@dataclass(frozen=True)
class ClientDispatchPlan:
    client_payloads: Sequence[ClientEmailPayload]
    targeted_clients: Sequence[models.Client]
    targeted_recipient_addresses: Sequence[str]
    combined_recipient_addresses: Sequence[str]