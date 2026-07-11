from __future__ import annotations

import copy
import datetime as dt
import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


MAX_NOTES = 20
MAX_TITLE_BYTES = 48
MAX_BODY_BYTES = 384
_NOTE_FIELDS = {"title", "body", "completed", "remind_at", "order"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


class NoteValidationError(ValueError):
    """Raised when a note mutation does not satisfy the repository contract."""


class VersionConflictError(ValueError):
    """Raised when a mutation was based on an older snapshot."""

    def __init__(self, snapshot: dict):
        self.snapshot = copy.deepcopy(snapshot)
        self.latest = copy.deepcopy(snapshot)
        self.version = snapshot.get("version", 0)
        super().__init__(f"base version is stale; current version is {self.version}")


class VersionedNoteStore:
    def __init__(self, path: Path, clock: Callable[[], Any] | None = None):
        self.path = Path(path)
        self._clock = clock or now_iso
        self._lock = threading.RLock()

    def read(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"version": 0, "notes": []}
            return copy.deepcopy(json.loads(self.path.read_text(encoding="utf-8")))

    def create(self, fields: Mapping[str, Any], base_version: int | None = None) -> dict:
        values = self._validated_fields(fields, allow_order=True)

        def apply(candidate: dict) -> None:
            notes = candidate.setdefault("notes", [])
            if len(notes) >= MAX_NOTES:
                raise NoteValidationError(f"at most {MAX_NOTES} notes are supported")
            notes.append(
                {
                    "id": uuid.uuid4().hex,
                    "title": values.get("title", ""),
                    "body": values.get("body", ""),
                    "completed": values.get("completed", False),
                    "remind_at": values.get("remind_at"),
                    "order": len(notes),
                }
            )
            self._canonicalize_orders(candidate)

        return self._mutate(apply, base_version)

    def patch(self, note_id: str, fields: Mapping[str, Any], base_version: int | None = None) -> dict:
        values = self._validated_fields(fields, allow_order=True)

        def apply(candidate: dict) -> None:
            note = self._find_note(candidate, note_id)
            before = copy.deepcopy(note)
            requested_order = values.get("order")
            for key, value in values.items():
                if key != "order":
                    note[key] = value
            if requested_order is not None and requested_order != note["order"]:
                if requested_order < 0 or requested_order >= len(candidate["notes"]):
                    raise NoteValidationError("order is outside the notes list")
                candidate["notes"].remove(note)
                candidate["notes"].insert(requested_order, note)
            self._canonicalize_orders(candidate)
            self._validate_note(note)
            if before == note and requested_order is not None:
                # The order request may have been numerically equal before normalization.
                self._canonicalize_orders(candidate)

        return self._mutate(apply, base_version)

    def delete(self, note_id: str, base_version: int | None = None) -> dict:
        def apply(candidate: dict) -> None:
            note = self._find_note(candidate, note_id)
            candidate["notes"].remove(note)
            self._canonicalize_orders(candidate)

        return self._mutate(apply, base_version)

    def reorder(self, ids: Sequence[str], base_version: int | None = None) -> dict:
        if isinstance(ids, (str, bytes)) or not isinstance(ids, Sequence):
            raise NoteValidationError("ids must be an ordered list of note IDs")
        requested_ids = list(ids)
        if any(not isinstance(note_id, str) for note_id in requested_ids):
            raise NoteValidationError("note IDs must be strings")
        if len(set(requested_ids)) != len(requested_ids):
            raise NoteValidationError("duplicate note IDs are not allowed")

        def apply(candidate: dict) -> None:
            notes_by_id = {note["id"]: note for note in candidate.get("notes", [])}
            if set(requested_ids) != set(notes_by_id) or len(requested_ids) != len(notes_by_id):
                raise NoteValidationError("reorder must include every existing note exactly once")
            candidate["notes"] = [notes_by_id[note_id] for note_id in requested_ids]
            self._canonicalize_orders(candidate)

        return self._mutate(apply, base_version)

    def _mutate(self, apply: Callable[[dict], None], base_version: int | None) -> dict:
        with self._lock:
            current = self.read()
            self._check_base_version(current, base_version)
            candidate = copy.deepcopy(current)
            apply(candidate)
            if candidate == current:
                return copy.deepcopy(current)

            timestamp = self._timestamp()
            previous_notes = {note["id"]: note for note in current.get("notes", [])}
            for note in candidate.get("notes", []):
                previous = previous_notes.get(note["id"])
                if previous is None or self._without_timestamp(previous) != self._without_timestamp(note):
                    note["updated_at"] = timestamp
            candidate["version"] = int(current.get("version", 0)) + 1
            candidate["updated_at"] = timestamp
            self._write(candidate)
            return copy.deepcopy(candidate)

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _check_base_version(self, current: dict, base_version: int | None) -> None:
        if base_version is None:
            return
        if isinstance(base_version, bool) or not isinstance(base_version, int):
            raise NoteValidationError("base_version must be an integer")
        if base_version != int(current.get("version", 0)):
            raise VersionConflictError(current)

    def _validated_fields(self, fields: Mapping[str, Any], allow_order: bool) -> dict:
        if not isinstance(fields, Mapping):
            raise NoteValidationError("fields must be an object")
        allowed = _NOTE_FIELDS if allow_order else _NOTE_FIELDS - {"order"}
        unknown = set(fields) - allowed
        if unknown:
            raise NoteValidationError(f"unsupported note fields: {sorted(unknown)}")

        values = dict(fields)
        if "title" in values:
            self._validate_text(values["title"], "title", MAX_TITLE_BYTES)
        if "body" in values:
            self._validate_text(values["body"], "body", MAX_BODY_BYTES)
        if "completed" in values and type(values["completed"]) is not bool:
            raise NoteValidationError("completed must be a boolean")
        if "remind_at" in values:
            self._validate_reminder(values["remind_at"])
        if "order" in values:
            if isinstance(values["order"], bool) or not isinstance(values["order"], int):
                raise NoteValidationError("order must be an integer")
        return values

    @staticmethod
    def _validate_text(value: Any, field: str, limit: int) -> None:
        if not isinstance(value, str):
            raise NoteValidationError(f"{field} must be a string")
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise NoteValidationError(f"{field} must be valid UTF-8") from exc
        if size > limit:
            raise NoteValidationError(f"{field} exceeds {limit} UTF-8 bytes")

    @staticmethod
    def _validate_reminder(value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            raise NoteValidationError("remind_at must be an ISO-8601 timestamp or null")
        try:
            dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise NoteValidationError("remind_at must be an ISO-8601 timestamp or null") from exc

    @staticmethod
    def _find_note(state: dict, note_id: str) -> dict:
        for note in state.get("notes", []):
            if note.get("id") == note_id:
                return note
        raise KeyError(note_id)

    @staticmethod
    def _canonicalize_orders(state: dict) -> None:
        for index, note in enumerate(state.get("notes", [])):
            note["order"] = int(index)

    @staticmethod
    def _validate_note(note: dict) -> None:
        VersionedNoteStore._validate_text(note.get("title"), "title", MAX_TITLE_BYTES)
        VersionedNoteStore._validate_text(note.get("body"), "body", MAX_BODY_BYTES)
        if type(note.get("completed")) is not bool:
            raise NoteValidationError("completed must be a boolean")
        VersionedNoteStore._validate_reminder(note.get("remind_at"))

    @staticmethod
    def _without_timestamp(note: dict) -> dict:
        result = copy.deepcopy(note)
        result.pop("updated_at", None)
        return result

    def _timestamp(self) -> str:
        value = self._clock()
        if isinstance(value, dt.datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, str):
            return value
        raise NoteValidationError("clock must return an ISO timestamp or datetime")
