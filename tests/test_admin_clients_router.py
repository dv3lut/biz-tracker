from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.api.schemas import ClientCreate, ClientUpdate
from app.api.routers.admin import clients_router as clients


class ClientRouterDelegationTests(TestCase):
    def setUp(self) -> None:
        self.session = MagicMock()

    @patch("app.api.routers.admin.clients_router.list_clients_action")
    def test_list_clients_delegates_to_handler(self, mock_action) -> None:
        mock_action.return_value = ["client"]

        result = clients.list_clients(session=self.session)

        mock_action.assert_called_once_with(self.session)
        self.assertEqual(result, ["client"])

    @patch("app.api.routers.admin.clients_router.get_client_action")
    def test_get_client_delegates_to_handler(self, mock_action) -> None:
        client_id = uuid4()
        mock_action.return_value = "client"

        result = clients.get_client(client_id=client_id, session=self.session)

        mock_action.assert_called_once_with(client_id=client_id, session=self.session)
        self.assertEqual(result, "client")

    @patch("app.api.routers.admin.clients_router.create_client_action")
    def test_create_client_delegates_to_handler(self, mock_action) -> None:
        payload = ClientCreate(name="Test", start_date=date.today())
        mock_action.return_value = "created"

        result = clients.create_client(payload=payload, session=self.session)

        mock_action.assert_called_once_with(payload=payload, session=self.session)
        self.assertEqual(result, "created")

    @patch("app.api.routers.admin.clients_router.update_client_action")
    def test_update_client_delegates_to_handler(self, mock_action) -> None:
        payload = ClientUpdate(name="New name")
        client_id = uuid4()
        mock_action.return_value = "updated"

        result = clients.update_client(client_id=client_id, payload=payload, session=self.session)

        mock_action.assert_called_once_with(client_id=client_id, payload=payload, session=self.session)
        self.assertEqual(result, "updated")

    @patch("app.api.routers.admin.clients_router.delete_client_action")
    def test_delete_client_delegates_to_handler(self, mock_action) -> None:
        client_id = uuid4()

        clients.delete_client(client_id=client_id, session=self.session)

        mock_action.assert_called_once_with(client_id=client_id, session=self.session)
