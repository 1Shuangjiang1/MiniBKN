"""Regression checks for public demo-loading helper."""

import httpx
import pytest

from scripts.seed_demo import load_example


def test_seed_posts_four_steps_and_passes_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200, json={"entries": []} if request.url.path.endswith("networks") else []
            )
        return httpx.Response(200, json={"ok": True})

    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = load_example("http://local", "supply_chain", "test-only-key")
    assert len(result) == 4
    assert len(requests) == 6
    assert requests[-1].url.path == "/api/v1/networks/supply_chain/builds"
    assert all(request.headers["x-api-key"] == "test-only-key" for request in requests)


def test_seed_stops_at_conflict_without_replacing_data(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200, json={"entries": []} if request.url.path.endswith("networks") else []
            )
        return httpx.Response(409, json={"message": "existing network"})

    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(RuntimeError, match="HTTP 409"):
        load_example("http://local", "crm")
    assert len(requests) == 3


def test_seed_checks_existing_network_before_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = {"entries": [{"id": "crm"}]} if request.url.path.endswith("networks") else []
        return httpx.Response(200, json=body)

    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(RuntimeError, match="already exists"):
        load_example("http://local", "crm")
    assert all(request.method == "GET" for request in requests)
