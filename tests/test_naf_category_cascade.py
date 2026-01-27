from __future__ import annotations

from unittest import TestCase

from app.db import models


class NafCategoryRelationshipTests(TestCase):
    def test_subcategories_relation_cascades_delete(self) -> None:
        rel = models.NafCategory.subcategories.property
        self.assertTrue(rel.passive_deletes)
        self.assertIn("delete", rel.cascade)


class NafSubCategoryRelationshipTests(TestCase):
    def test_subscriptions_relation_cascades_delete(self) -> None:
        rel = models.NafSubCategory.subscriptions.property
        self.assertTrue(rel.passive_deletes)
        self.assertIn("delete", rel.cascade)
