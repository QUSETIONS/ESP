from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.meeting_server import meeting_server


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def request_error(url: str, method: str, payload: dict | None = None) -> urllib.error.HTTPError:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(request, timeout=5)
    return exc_info.value


def error_payload(error: urllib.error.HTTPError) -> dict:
    return json.loads(error.read().decode("utf-8"))


def sse_events(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=5) as response:
        raw = response.read().decode("utf-8")
    events: list[dict] = []
    for block in raw.strip().split("\n\n"):
        if not block:
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append({"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])})
    return events


@pytest.fixture()
def server(tmp_path: Path):
    class Handler(meeting_server.MeetingHandler):
        pass

    Handler.data_path = tmp_path / "meeting.json"
    Handler.file_root = tmp_path / "files"
    Handler.note_store_path = tmp_path / "notes.json"
    Handler.reset_realtime_runtime()
    Handler.note_store = None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_notes_routes_create_read_update_reorder_and_delete(server):
    assert request_json(server + "/notes") == {"version": 0, "notes": []}
    assert request_json(server + "/notes/version") == {"version": 0, "updated_at": None}

    created = request_json(server + "/notes", "POST", {"title": "A", "body": "First", "order": 9})
    first_id = created["note"]["id"]
    assert created["version"] == 1
    assert created["note"]["order"] == 0
    assert created["data"]["notes"] == [created["note"]]

    second = request_json(server + "/notes", "POST", {"title": "B"})
    second_id = second["note"]["id"]
    patched = request_json(server + f"/notes/{first_id}", "PATCH", {"completed": True, "base_version": 2})
    assert patched["version"] == 3
    assert patched["note"]["completed"] is True

    reordered = request_json(server + "/notes/reorder", "PUT", {"ids": [second_id, first_id], "base_version": 3})
    assert reordered["version"] == 4
    assert [note["id"] for note in reordered["data"]["notes"]] == [second_id, first_id]

    deleted = request_json(server + f"/notes/{first_id}", "DELETE", {"base_version": 4})
    assert deleted["version"] == 5
    assert [note["id"] for note in deleted["data"]["notes"]] == [second_id]

    assert request_json(server + "/notes/version") == {"version": 5, "updated_at": deleted["data"]["updated_at"]}


def test_notes_validation_and_unknown_ids_are_mapped_to_http_errors(server):
    invalid = request_error(server + "/notes", "POST", {"title": "x" * 49})
    assert invalid.code == 400
    assert error_payload(invalid)["ok"] is False

    missing_patch = request_error(server + "/notes/missing", "PATCH", {"title": "A"})
    missing_delete = request_error(server + "/notes/missing", "DELETE", {})
    assert missing_patch.code == 404
    assert missing_delete.code == 404

    invalid_reorder = request_error(server + "/notes/reorder", "PUT", {"ids": ["duplicate", "duplicate"]})
    assert invalid_reorder.code == 400


def test_stale_patch_returns_latest_snapshot(server):
    created = request_json(server + "/notes", "POST", {"title": "A"})
    request_json(server + "/notes", "POST", {"title": "B"})

    error = request_error(
        server + "/notes/" + created["note"]["id"],
        "PATCH",
        {"title": "C", "base_version": created["version"]},
    )

    assert error.code == 409
    payload = error_payload(error)
    assert payload["data"]["version"] == created["version"] + 1
    assert payload["data"]["notes"][0]["title"] == "A"


def test_notes_events_are_published_once_per_changed_version(server):
    created = request_json(server + "/notes", "POST", {"title": "A"})
    note_id = created["note"]["id"]
    request_json(server + f"/notes/{note_id}", "PATCH", {"completed": True})
    request_json(server + f"/notes/{note_id}", "PATCH", {"completed": True})
    request_json(server + f"/notes/{note_id}", "DELETE", {})

    events = [event for event in sse_events(server + "/api/events") if event["event"] == "notes"]
    assert [event["id"] for event in events] == [1, 2, 3]
    assert [event["data"]["version"] for event in events] == [1, 2, 3]
    assert events[-1]["data"]["notes"] == []


def test_concurrent_noop_does_not_duplicate_notes_event(server, monkeypatch):
    created = request_json(server + "/notes", "POST", {"title": "A"})
    note_id = created["note"]["id"]
    both_mutations_reached = threading.Barrier(2)
    real_mutate = meeting_server.VersionedNoteStore._mutate

    def coordinated_mutate(self, apply, base_version):
        both_mutations_reached.wait(timeout=5)
        return real_mutate(self, apply, base_version)

    monkeypatch.setattr(meeting_server.VersionedNoteStore, "_mutate", coordinated_mutate)
    responses: list[dict] = []
    errors: list[Exception] = []

    def patch_completed():
        try:
            responses.append(request_json(server + f"/notes/{note_id}", "PATCH", {"completed": True}))
        except Exception as error:  # pragma: no cover - failures are asserted below.
            errors.append(error)

    requests = [threading.Thread(target=patch_completed) for _ in range(2)]
    for request in requests:
        request.start()
    for request in requests:
        request.join(timeout=5)

    assert not errors
    assert all(not request.is_alive() for request in requests)
    assert [response["version"] for response in responses] == [2, 2]
    events = [event for event in sse_events(server + "/api/events") if event["event"] == "notes"]
    assert [event["data"]["version"] for event in events] == [1, 2]


def test_options_advertises_note_mutation_methods(server):
    request = urllib.request.Request(server + "/notes", method="OPTIONS")
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.headers["Access-Control-Allow-Methods"] == "GET, POST, PATCH, DELETE, PUT, OPTIONS"
