from __future__ import annotations

from datetime import date
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from app.utils import dates


class DatesUtilsTests(TestCase):
    def test_parse_date_valid(self) -> None:
        self.assertEqual(dates.parse_date("2026-02-08"), date(2026, 2, 8))

    def test_parse_date_invalid(self) -> None:
        self.assertIsNone(dates.parse_date("not-a-date"))
        self.assertIsNone(dates.parse_date(None))

    def test_parse_datetime_none(self) -> None:
        self.assertIsNone(dates.parse_datetime(None))

    def test_parse_datetime_fallback(self) -> None:
        value = dates.parse_datetime("2026-02-08T10:11:12")
        self.assertIsNotNone(value)

        class FakeDateTime:
            @staticmethod
            def fromisoformat(_value: str):
                raise ValueError("boom")

            @staticmethod
            def strptime(value: str, fmt: str):
                return datetime.strptime(value, fmt)

        with patch("app.utils.dates.datetime", FakeDateTime):
            legacy = dates.parse_datetime("2026-02-08T10:11:12")
            self.assertIsNotNone(legacy)

        self.assertIsNone(dates.parse_datetime("invalid"))

        class FailingDateTime:
            @staticmethod
            def fromisoformat(_value: str):
                raise ValueError("boom")

            @staticmethod
            def strptime(_value: str, _fmt: str):
                raise ValueError("boom")

        with patch("app.utils.dates.datetime", FailingDateTime):
            self.assertIsNone(dates.parse_datetime("2026-02-08T10:11:12"))

    def test_subtract_months_clamps_day(self) -> None:
        reference = date(2026, 3, 31)
        result = dates.subtract_months(reference, 1)
        self.assertEqual(result, date(2026, 2, 28))

    def test_subtract_months_zero_returns_reference(self) -> None:
        reference = date(2026, 3, 31)
        self.assertEqual(dates.subtract_months(reference, 0), reference)

    def test_utcnow_is_naive(self) -> None:
        value = dates.utcnow()
        self.assertIsNone(value.tzinfo)
