"""Compat: middleware rate limiting import path.

Le middleware d'API (rate limiting entrant) vit désormais dans
`app/api/middlewares/rate_limit_middleware.py`.

Ce module est conservé uniquement pour éviter de casser d'éventuels imports
internes/externes.
"""

from __future__ import annotations

from .rate_limit_middleware import RateLimitMiddleware, RateLimitPolicy

__all__ = ["RateLimitMiddleware", "RateLimitPolicy"]
