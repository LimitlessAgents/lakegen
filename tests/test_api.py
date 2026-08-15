"""API / BFF tests with mocked CatalogService and AgentRunner."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from lakegen.agent import StopReason
from lakegen.api.app import create_app
from lakegen.api.auth.local import LocalAuth
from lakegen.api.run.runner import AgentEvent, AgentEventType, TurnResult
from lakegen.core.catalog.service import CatalogInfo
from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode

_SESSION_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture()
def catalogs() -> MagicMock:
    svc = MagicMock()
    svc.list.return_value = [
        CatalogInfo(
            name="prod",
            connected=True,
            lakehouse="iceberg",
            catalog_type="rest",
            warehouse="s3://wh",
        )
    ]
    svc.get.return_value = CatalogInfo(
        name="prod",
        connected=True,
        lakehouse="iceberg",
        catalog_type="rest",
        warehouse="s3://wh",
    )
    svc.add.side_effect = lambda spec: CatalogInfo(
        name=spec.name,
        connected=True,
        lakehouse=spec.lakehouse,
        catalog_type=spec.catalog_type,
        warehouse=spec.warehouse,
    )
    return svc


@pytest.fixture()
def agent_runner() -> MagicMock:
    runner = MagicMock()
    runner.create_session.return_value = _SESSION_ID

    def _run_turn(
        session_id,
        user_text,
        *,
        owner_id=None,
        catalog_name=None,
        model=None,
        provider=None,
        on_event=None,
    ):
        if on_event is not None:
            on_event(
                AgentEvent(
                    type=AgentEventType.TEXT_DELTA,
                    data={"text": "hello"},
                )
            )
            on_event(
                AgentEvent(
                    type=AgentEventType.TURN_DONE,
                    data={
                        "final_message": "hello",
                        "stop_reason": StopReason.COMPLETED.value,
                    },
                )
            )
        return TurnResult(
            final_message="hello",
            stop_reason=StopReason.COMPLETED,
        )

    runner.run_turn.side_effect = _run_turn
    return runner


@pytest.fixture()
def client(catalogs, agent_runner) -> TestClient:
    app = create_app(
        authenticator=LocalAuth(),
        agent_runner=agent_runner,
        catalogs_service=catalogs,
        cors_origins=["http://localhost:3000"],
        max_in_flight_turns=2,
    )
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_list_catalogs(client: TestClient, catalogs: MagicMock) -> None:
    res = client.get("/v1/catalogs")
    assert res.status_code == 200
    assert res.json() == [
        {
            "name": "prod",
            "connected": True,
            "lakehouse": "iceberg",
            "catalog_type": "rest",
            "warehouse": "s3://wh",
        }
    ]
    catalogs.list.assert_called_once()


def test_add_catalog(client: TestClient, catalogs: MagicMock) -> None:
    body = {
        "lakehouse": "iceberg",
        "catalog_type": "rest",
        "name": "dev",
        "warehouse": "s3://dev",
        "rest_catalog_url": "http://catalog.example",
    }
    res = client.post("/v1/catalogs", json=body)
    assert res.status_code == 201
    assert res.json()["name"] == "dev"
    catalogs.add.assert_called_once()


def test_add_catalog_invalid(client: TestClient) -> None:
    res = client.post("/v1/catalogs", json={"name": "x"})
    assert res.status_code == 400
    assert res.json() == {
        "code": "INVALID_ARGUMENT",
        "message": "Request validation failed.",
    }


def test_get_catalog_not_found(client: TestClient, catalogs: MagicMock) -> None:
    catalogs.get.side_effect = BaseError(
        ErrorCode.NOT_FOUND,
        "Catalog 'missing' is not registered.",
    )
    res = client.get("/v1/catalogs/missing")
    assert res.status_code == 404
    assert res.json() == {
        "code": "NOT_FOUND",
        "message": "Catalog 'missing' is not registered.",
    }


def test_server_error_hides_internal_error_context(
    client: TestClient, catalogs: MagicMock
) -> None:
    catalogs.get.side_effect = BaseError(
        ErrorCode.CONNECTION_FAILED,
        "Connection to internal-host:8181 failed.",
        details={"credential": "secret"},
    )
    res = client.get("/v1/catalogs/prod")
    assert res.status_code == 502
    assert res.json() == {
        "code": "CONNECTION_FAILED",
        "message": "The service is temporarily unavailable.",
    }


def test_fastapi_http_error_uses_service_error_contract(client: TestClient) -> None:
    res = client.get("/missing")
    assert res.status_code == 404
    assert res.json() == {"code": "NOT_FOUND", "message": "Not Found"}


def test_delete_catalog(client: TestClient, catalogs: MagicMock) -> None:
    res = client.delete("/v1/catalogs/prod")
    assert res.status_code == 204
    catalogs.delete.assert_called_once_with("prod")


def test_create_session(client: TestClient, agent_runner: MagicMock) -> None:
    res = client.post("/v1/sessions")
    assert res.status_code == 201
    assert res.json() == {"id": _SESSION_ID}
    agent_runner.create_session.assert_called_once_with(owner_id="local")


def test_delete_session(client: TestClient, agent_runner: MagicMock) -> None:
    res = client.delete(f"/v1/sessions/{_SESSION_ID}")
    assert res.status_code == 204
    agent_runner.delete_session.assert_called_once_with(
        _SESSION_ID, owner_id="local"
    )


def test_delete_session_passes_x_user(
    client: TestClient, agent_runner: MagicMock
) -> None:
    res = client.delete(
        f"/v1/sessions/{_SESSION_ID}", headers={"X-User": "alice"}
    )
    assert res.status_code == 204
    agent_runner.delete_session.assert_called_once_with(
        _SESSION_ID, owner_id="alice"
    )


def test_local_auth_x_user_header(client: TestClient, agent_runner: MagicMock) -> None:
    res = client.post("/v1/sessions", headers={"X-User": "alice"})
    assert res.status_code == 201
    agent_runner.create_session.assert_called_once_with(owner_id="alice")


def test_turn_sse(client: TestClient, agent_runner: MagicMock) -> None:
    with client.stream(
        "POST",
        f"/v1/sessions/{_SESSION_ID}/turns",
        json={
            "text": "hi",
            "catalog_name": "prod",
            "model": "test-model",
        },
    ) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())

    assert "event: text_delta" in body
    assert "event: turn_done" in body
    assert '"text": "hello"' in body
    agent_runner.run_turn.assert_called_once()
    kwargs = agent_runner.run_turn.call_args.kwargs
    assert agent_runner.run_turn.call_args.args[0] == _SESSION_ID
    assert agent_runner.run_turn.call_args.args[1] == "hi"
    assert kwargs["owner_id"] == "local"
    assert kwargs["catalog_name"] == "prod"
    assert kwargs["model"] == "test-model"


def test_turn_sse_error(client: TestClient, agent_runner: MagicMock) -> None:
    def _boom(*_a, **_k):
        raise BaseError(ErrorCode.NOT_FOUND, "Session not found.")

    agent_runner.run_turn.side_effect = _boom
    with client.stream(
        "POST",
        f"/v1/sessions/{_SESSION_ID}/turns",
        json={"text": "hi", "catalog_name": "prod"},
    ) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())

    assert "event: error" in body
    assert '"message": "Session not found."' in body
    assert f'"code": "{ErrorCode.NOT_FOUND.value}"' in body


def test_local_run_adapter_create_and_turn() -> None:
    from lakegen.api.run.local import LocalRunAdapter
    from lakegen.session import SessionManager

    manager = MagicMock(spec=SessionManager)
    session = MagicMock()
    session.id = _SESSION_ID
    session.state.owner_id = "alice"
    manager.create.return_value = session

    def _send(text, *, catalog_name=None, model=None, provider=None, stream=False, on_chunk=None):
        if on_chunk is not None:
            from lakegen.inference import StreamChunk

            on_chunk(StreamChunk(text="yo"))
            on_chunk(StreamChunk(done=True))
        return MagicMock(
            final_message="yo",
            stop_reason=StopReason.COMPLETED,
        )

    session.send.side_effect = _send
    manager.get.return_value = session

    adapter = LocalRunAdapter(manager=manager)
    session_id = adapter.create_session(owner_id="alice")
    assert session_id == _SESSION_ID
    manager.create.assert_called_once()
    assert manager.create.call_args.kwargs["owner_id"] == "alice"

    events: list[AgentEvent] = []
    result = adapter.run_turn(
        _SESSION_ID,
        "hi",
        owner_id="alice",
        catalog_name="prod",
        model="m",
        on_event=events.append,
    )
    assert result.final_message == "yo"
    session.send.assert_called_once()
    assert session.send.call_args.kwargs["catalog_name"] == "prod"
    assert session.send.call_args.kwargs["model"] == "m"
    assert [e.type for e in events] == [
        AgentEventType.TEXT_DELTA,
        AgentEventType.TURN_DONE,
    ]


def test_local_run_adapter_rejects_non_owner_delete() -> None:
    from lakegen.api.run.local import LocalRunAdapter
    from lakegen.session import SessionManager

    manager = MagicMock(spec=SessionManager)
    session = MagicMock()
    session.state.owner_id = "alice"
    manager.get.return_value = session

    adapter = LocalRunAdapter(manager=manager)
    with pytest.raises(BaseError) as exc_info:
        adapter.delete_session(_SESSION_ID, owner_id="bob")
    assert exc_info.value.code == ErrorCode.NOT_FOUND
    manager.delete.assert_not_called()


def test_local_run_adapter_rejects_non_owner_turn() -> None:
    from lakegen.api.run.local import LocalRunAdapter
    from lakegen.session import SessionManager

    manager = MagicMock(spec=SessionManager)
    session = MagicMock()
    session.state.owner_id = "alice"
    manager.get.return_value = session

    adapter = LocalRunAdapter(manager=manager)
    with pytest.raises(BaseError) as exc_info:
        adapter.run_turn(_SESSION_ID, "hi", owner_id="bob")
    assert exc_info.value.code == ErrorCode.NOT_FOUND
    session.send.assert_not_called()
