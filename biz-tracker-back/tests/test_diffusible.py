"""Tests for app.utils.diffusible module."""
from __future__ import annotations

from unittest import TestCase

from app.utils.diffusible import any_name_non_diffusible, is_non_diffusible


class DiffusibleTests(TestCase):
    def test_is_non_diffusible_returns_false_for_none(self) -> None:
        self.assertFalse(is_non_diffusible(None))

    def test_is_non_diffusible_returns_false_for_empty_string(self) -> None:
        self.assertFalse(is_non_diffusible(""))

    def test_is_non_diffusible_returns_false_for_normal_name(self) -> None:
        self.assertFalse(is_non_diffusible("Jean Dupont"))
        self.assertFalse(is_non_diffusible("BOULANGERIE DES CO'PAINS"))

    def test_is_non_diffusible_returns_true_for_nd_marker(self) -> None:
        self.assertTrue(is_non_diffusible("[ND]"))
        self.assertTrue(is_non_diffusible("[nd]"))  # Case insensitive
        self.assertTrue(is_non_diffusible("Nom [ND] Prénom"))

    def test_is_non_diffusible_returns_true_for_non_diffusible_text(self) -> None:
        self.assertTrue(is_non_diffusible("NON DIFFUSIBLE"))
        self.assertTrue(is_non_diffusible("non diffusible"))  # Case insensitive
        self.assertTrue(is_non_diffusible("Établissement NON DIFFUSIBLE"))
        self.assertTrue(is_non_diffusible("NON-DIFFUSIBLE"))
        self.assertTrue(is_non_diffusible("[NON-DIFFUSIBLE]"))

    def test_any_name_non_diffusible_returns_false_when_all_names_are_normal(self) -> None:
        self.assertFalse(any_name_non_diffusible("Jean", "Dupont", None))

    def test_any_name_non_diffusible_returns_true_if_any_name_has_nd(self) -> None:
        self.assertTrue(any_name_non_diffusible("Jean", "[ND]", "Martin"))
        self.assertTrue(any_name_non_diffusible(None, "NON DIFFUSIBLE"))

    def test_any_name_non_diffusible_returns_false_for_empty_args(self) -> None:
        self.assertFalse(any_name_non_diffusible())
