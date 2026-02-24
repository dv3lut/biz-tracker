"""Unit tests for the AlertService filtering logic."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.alerts.alert_service import AlertService
from app.utils.dates import subtract_months


class AlertServiceFilteringTests(unittest.TestCase):
    """Ensure alert creation filters correctly based on Google status."""

    def setUp(self) -> None:
        self.session = MagicMock()
        self.run = SimpleNamespace(id="run-1", scope_key="restaurants")

    @contextmanager
    def _patched_dependencies(
        self,
        *,
        active_clients: list[SimpleNamespace] | None = None,
        admin_recipients: list[str] | None = None,
        client_emails: list[str] | None = None,
        assignment_map: dict | None = None,
        filters_configured: bool = False,
        dispatch_result: SimpleNamespace | None = None,
    ):
        stack = ExitStack()
        email_service = MagicMock()
        email_service.is_enabled.return_value = True
        email_service.is_configured.return_value = True
        stack.enter_context(patch("app.services.alerts.alert_service.EmailService", return_value=email_service))
        stack.enter_context(
            patch(
                "app.services.alerts.alert_service.get_active_clients",
                return_value=active_clients or [],
            )
        )
        stack.enter_context(
            patch(
                "app.services.alerts.alert_service.get_admin_emails",
                return_value=admin_recipients or [],
            )
        )
        stack.enter_context(
            patch(
                "app.services.alerts.alert_service.assign_establishments_to_clients",
                return_value=(assignment_map or {}, filters_configured),
            )
        )
        stack.enter_context(
            patch(
                "app.services.alerts.alert_service.collect_client_emails",
                return_value=client_emails or [],
            )
        )
        default_result = SimpleNamespace(delivered=[], failed=[], sent_at=None)
        dispatch_mock = MagicMock(
            return_value=dispatch_result or default_result
        )
        stack.enter_context(
            patch(
                "app.services.alerts.alert_service.dispatch_email_to_clients",
                dispatch_mock,
            )
        )
        log_mock = stack.enter_context(patch("app.services.alerts.alert_service.log_event"))
        try:
            yield SimpleNamespace(dispatch_mock=dispatch_mock, log_mock=log_mock, email_service=email_service)
        finally:
            stack.close()

    def _make_establishment(self, status: str, *, suffix: str) -> SimpleNamespace:
        return SimpleNamespace(
            siret=f"0000000000000{suffix}",
            siren=f"0000000000{suffix}",
            name=f"Etablissement {suffix}",
            google_check_status="found",
            naf_code=None,
            naf_libelle=None,
            date_creation=None,
            google_listing_origin_at=None,
            google_listing_age_status=status,
            numero_voie=None,
            type_voie=None,
            libelle_voie=None,
            complement_adresse=None,
            indice_repetition=None,
            code_postal="75000",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            code_commune="75101",
            code_pays="FR",
            libelle_pays="France",
            google_place_url="https://maps.google.com/?cid=123",
            google_place_id="ChIJ123",
            google_match_confidence=0.95,
            date_dernier_traitement_etablissement=None,
        )

    def _make_client(self, *, email: str | None = "client@example.com") -> SimpleNamespace:
        recipients = [SimpleNamespace(email=email)] if email is not None else [SimpleNamespace(email=None)]
        return SimpleNamespace(
            id=uuid4(),
            name="Client",
            recipients=recipients,
            subscriptions=[],
            listing_statuses=["recent_creation"],
            start_date=date.today(),
            end_date=None,
        )

    def test_returns_empty_when_no_found_listing(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]
        establishments[0].google_check_status = "pending"
        establishments[1].google_check_status = "not_found"

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(alerts, [])
        self.session.add.assert_not_called()

    def test_keeps_all_found_listings(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 2)
        self.assertEqual(self.session.add.call_count, 2)

    def test_excludes_type_mismatch_from_alerts(self) -> None:
        establishments = [
            self._make_establishment("recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]
        establishments[1].google_check_status = "type_mismatch"

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(self.session.add.call_count, 1)

    def test_client_notifications_can_be_disabled(self) -> None:
        establishments = [self._make_establishment("recent_creation", suffix="1")]

        with self._patched_dependencies() as deps:
            service = AlertService(
                self.session,
                self.run,
                client_notifications_enabled=False,
            )
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        deps.dispatch_mock.assert_not_called()
        reasons = [kwargs.get("reason") for _, kwargs in deps.log_mock.call_args_list]
        self.assertIn("client_notifications_disabled", [reason for reason in reasons if reason])

    def test_sends_digest_when_no_establishments(self) -> None:
        client = SimpleNamespace(
            id="client-1",
            name="Client A",
            recipients=[SimpleNamespace(email="client@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )

        with self._patched_dependencies(active_clients=[client]) as deps:
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts([])

        self.assertEqual(alerts, [])
        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].subject, "Business tracker · Rapport quotidien")

    def test_targeted_clients_receive_zero_digest(self) -> None:
        client_a = SimpleNamespace(
            id=uuid4(),
            name="Client A",
            recipients=[SimpleNamespace(email="a@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        client_b = SimpleNamespace(
            id=uuid4(),
            name="Client B",
            recipients=[SimpleNamespace(email="b@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )

        with self._patched_dependencies(active_clients=[client_a, client_b]) as deps:
            service = AlertService(
                self.session,
                self.run,
                target_client_ids=[client_a.id],
            )
            service.create_google_alerts([])

        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].client.id, client_a.id)

    def test_targeted_clients_receive_zero_digest_even_when_other_matches_exist(self) -> None:
        client_a = SimpleNamespace(
            id=uuid4(),
            name="Client A",
            recipients=[SimpleNamespace(email="a@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        client_b = SimpleNamespace(
            id=uuid4(),
            name="Client B",
            recipients=[SimpleNamespace(email="b@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        establishment = self._make_establishment("recent_creation", suffix="5")

        with self._patched_dependencies(
            active_clients=[client_a, client_b],
            assignment_map={},
            filters_configured=True,
        ) as deps:
            service = AlertService(
                self.session,
                self.run,
                target_client_ids=[client_a.id],
            )
            service.create_google_alerts([establishment])

        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].client.id, client_a.id)

    def test_previous_month_day_uses_replay_date(self) -> None:
        client = SimpleNamespace(
            id=uuid4(),
            name="Client",
            recipients=[SimpleNamespace(email="client@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        replay_date = date(2026, 1, 24)
        run = SimpleNamespace(id="run-1", scope_key="restaurants", replay_for_date=replay_date, started_at=datetime(2026, 1, 31, 10, 0, 0))
        self.session.execute.return_value.scalars.return_value = []

        with (
            self._patched_dependencies(active_clients=[client]) as deps,
            patch.object(AlertService, "_has_previous_successful_run", return_value=True),
            patch("app.services.alerts.alert_service.get_alert_email_settings", return_value=SimpleNamespace(include_previous_month_day_alerts=True)),
            patch("app.services.alerts.alert_service.render_client_email", return_value=("", "")) as render_mock,
        ):
            service = AlertService(self.session, run)
            service.create_google_alerts([])

        self.assertTrue(render_mock.called)
        previous_date = render_mock.call_args.kwargs.get("previous_month_day_date")
        self.assertEqual(previous_date, subtract_months(replay_date, 1))

    def test_admin_notifications_can_be_disabled(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="9")

        with self._patched_dependencies(admin_recipients=["admin@example.com"]) as deps:
            service = AlertService(
                self.session,
                self.run,
                admin_notifications_enabled=False,
            )
            service.create_google_alerts([establishment])

        deps.email_service.send.assert_not_called()

    def test_client_copy_to_admins_kept_when_admin_summary_disabled(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="90")
        client = self._make_client(email="client@example.com")
        client.include_admins_in_client_alerts = True

        with self._patched_dependencies(
            active_clients=[client],
            admin_recipients=["admin@example.com"],
            assignment_map={client.id: [establishment]},
            client_emails=["client@example.com"],
            dispatch_result=SimpleNamespace(delivered=[client], failed=[], sent_at=None),
        ) as deps:
            service = AlertService(
                self.session,
                self.run,
                admin_notifications_enabled=False,
            )
            service.create_google_alerts([establishment])

        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(payloads[0].extra_recipients, ["admin@example.com"])
        deps.email_service.send.assert_not_called()

    def test_client_notifications_skip_when_email_disabled(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="3")

        with self._patched_dependencies(admin_recipients=["admin@example.com"]) as deps:
            deps.email_service.is_enabled.return_value = False
            service = AlertService(self.session, self.run)
            service.create_google_alerts([establishment])

        reasons = [kwargs.get("reason") for _, kwargs in deps.log_mock.call_args_list if "reason" in kwargs]
        assert "email_disabled" in reasons

    def test_admin_notifications_sent_and_logged(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="4")

        with self._patched_dependencies(admin_recipients=["admin@example.com"]) as deps:
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts([establishment])

        deps.email_service.send.assert_called_once()
        assert all(alert.sent_at is not None for alert in alerts)

    def test_admin_notification_failure_is_logged(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="5")

        with self._patched_dependencies(admin_recipients=["admin@example.com"]) as deps:
            deps.email_service.send.side_effect = RuntimeError("smtp down")
            service = AlertService(self.session, self.run)
            service.create_google_alerts([establishment])

        events = [args[0] for args, _ in deps.log_mock.call_args_list]
        assert "alerts.email.admin_error" in events

    def test_prepare_client_dispatch_aborts_when_email_disabled(self) -> None:
        service = AlertService(self.session, self.run)

        plan, reason = service._prepare_client_dispatch(
            [],
            {},
            [],
            email_enabled=False,
            email_configured=True,
            has_previous_success=True,
        )

        self.assertIsNone(plan)
        self.assertEqual(reason, "email_disabled")

    def test_prepare_client_dispatch_requires_previous_success_and_clients(self) -> None:
        service = AlertService(self.session, self.run)

        plan, reason = service._prepare_client_dispatch(
            [],
            {},
            [],
            email_enabled=True,
            email_configured=True,
            has_previous_success=False,
        )
        self.assertIsNone(plan)
        self.assertEqual(reason, "initial_sync")

        with patch("app.services.alerts.alert_service.get_active_clients", return_value=[]):
            plan, reason = service._prepare_client_dispatch(
                [],
                {},
                [],
                email_enabled=True,
                email_configured=True,
                has_previous_success=True,
            )

        self.assertIsNone(plan)
        self.assertEqual(reason, "no_clients")

    def test_prepare_client_dispatch_handles_invalid_targets_and_missing_recipients(self) -> None:
        client = self._make_client()
        service = AlertService(self.session, self.run)

        with patch("app.services.alerts.alert_service.get_active_clients", return_value=[client]):
            plan, reason = service._prepare_client_dispatch(
                [],
                {},
                [],
                email_enabled=True,
                email_configured=True,
                has_previous_success=True,
                target_client_ids=["not-a-uuid"],
            )

        self.assertIsNone(plan)
        self.assertEqual(reason, "no_targeted_clients")

        target_id = uuid4()
        recipientless = self._make_client(email=None)
        recipientless.id = target_id
        with patch("app.services.alerts.alert_service.get_active_clients", return_value=[recipientless]):
            plan, reason = service._prepare_client_dispatch(
                [],
                {},
                [],
                email_enabled=True,
                email_configured=True,
                has_previous_success=True,
                target_client_ids=[target_id],
            )

        self.assertIsNone(plan)
        self.assertEqual(reason, "no_active_recipients")

    def test_prepare_client_dispatch_requires_matches_when_filters_configured(self) -> None:
        client = self._make_client()
        service = AlertService(self.session, self.run)

        with ExitStack() as stack:
            stack.enter_context(patch("app.services.alerts.alert_service.get_active_clients", return_value=[client]))
            stack.enter_context(
                patch(
                    "app.services.alerts.alert_service.assign_establishments_to_clients",
                    return_value=({}, True),
                )
            )
            plan, reason = service._prepare_client_dispatch(
                [self._make_establishment("recent_creation", suffix="7")],
                {},
                [],
                email_enabled=True,
                email_configured=True,
                has_previous_success=True,
            )

        self.assertIsNone(plan)
        self.assertEqual(reason, "no_matching_filters")

    def test_prepare_client_dispatch_builds_plan_with_combined_recipients(self) -> None:
        client = self._make_client(email="client@example.com")
        establishment = self._make_establishment("recent_creation", suffix="8")
        service = AlertService(self.session, self.run)

        with ExitStack() as stack:
            stack.enter_context(patch("app.services.alerts.alert_service.get_active_clients", return_value=[client]))
            stack.enter_context(
                patch(
                    "app.services.alerts.alert_service.assign_establishments_to_clients",
                    return_value=({client.id: [establishment]}, False),
                )
            )
            stack.enter_context(
                patch(
                    "app.services.alerts.alert_service.summarize_client_filters",
                    return_value=SimpleNamespace(listing_statuses=[], naf_codes=[]),
                )
            )
            stack.enter_context(
                patch(
                    "app.services.alerts.alert_service.render_client_email",
                    return_value=("plain", "<p>html</p>"),
                )
            )
            stack.enter_context(
                patch(
                    "app.services.alerts.alert_service.collect_client_emails",
                    return_value=["client@example.com"],
                )
            )
            plan, reason = service._prepare_client_dispatch(
                [establishment],
                {},
                ["admin@example.com"],
                email_enabled=True,
                email_configured=True,
                has_previous_success=True,
            )

        self.assertIsNone(reason)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.targeted_clients, [client])
        self.assertEqual(plan.targeted_recipient_addresses, ["client@example.com"])
        self.assertEqual(plan.combined_recipient_addresses, ["admin@example.com", "client@example.com"])

    def test_dispatch_success_sets_sent_timestamp_and_logs(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="10")
        client = self._make_client()
        dispatch_result = SimpleNamespace(
            delivered=[client],
            failed=[(client, Exception("partial"))],
            sent_at=datetime(2024, 1, 2, 12, 0, 0),
        )

        with self._patched_dependencies(
            active_clients=[client],
            assignment_map={client.id: [establishment]},
            client_emails=["client@example.com"],
            dispatch_result=dispatch_result,
        ) as deps:
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts([establishment])

        assert all(alert.sent_at == dispatch_result.sent_at for alert in alerts)
        events = [args[0] for args, _ in deps.log_mock.call_args_list]
        assert "alerts.email.sent" in events

    def test_dispatch_failures_log_skip_reason(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="11")
        client = self._make_client()
        dispatch_result = SimpleNamespace(
            delivered=[],
            failed=[(client, Exception("boom"))],
            sent_at=None,
        )

        with self._patched_dependencies(
            active_clients=[client],
            assignment_map={client.id: [establishment]},
            client_emails=["client@example.com"],
            dispatch_result=dispatch_result,
        ) as deps:
            service = AlertService(self.session, self.run)
            service.create_google_alerts([establishment])

        events = [args[0] for args, _ in deps.log_mock.call_args_list]
        assert "alerts.email.skipped" in events

    def test_linkedin_only_establishment_is_included_in_alerts(self) -> None:
        """Test that establishments with LinkedIn profiles but no Google are included in alerts."""
        # Create establishment with google_check_status = "not_found" (no Google)
        establishment = self._make_establishment("not_recent_creation", suffix="20")
        establishment.google_check_status = "not_found"
        
        # Add director with LinkedIn profile
        director = SimpleNamespace(
            is_physical_person=True,
            linkedin_profile_url="https://linkedin.com/in/jane-doe",
            linkedin_profile_data={"name": "Jane Doe"},
        )
        establishment.directors = [director]
        
        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts([establishment])
        
        # Should create 1 alert (LinkedIn-only)
        self.assertEqual(len(alerts), 1)
        self.session.add.assert_called_once()
        
        # Alert should have has_linkedin=True and has_google=False
        alert = alerts[0]
        self.assertTrue(alert.payload["has_linkedin"])
        self.assertFalse(alert.payload["has_google"])


if __name__ == "__main__":
    unittest.main()
