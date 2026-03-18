from __future__ import annotations

import json
from pathlib import Path

from ..models import HistoryRecord

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class HistoryService:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _record_path(self, record_id: str) -> Path:
        safe_id = record_id.replace("/", "_").replace("..", "_")
        return DATA_DIR / f"{safe_id}.json"

    def list_records(self) -> list[HistoryRecord]:
        records: list[HistoryRecord] = []
        for f in DATA_DIR.glob("*.json"):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                records.append(HistoryRecord(**raw))
            except Exception:
                continue
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records

    def save_record(self, record: HistoryRecord) -> HistoryRecord:
        path = self._record_path(record.id)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get_record(self, record_id: str) -> HistoryRecord | None:
        path = self._record_path(record_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return HistoryRecord(**raw)
        except Exception:
            return None

    def delete_record(self, record_id: str) -> bool:
        path = self._record_path(record_id)
        if path.exists():
            path.unlink()
            return True
        return False
