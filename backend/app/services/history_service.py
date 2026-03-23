from __future__ import annotations

import json
from pathlib import Path

from ..models import (
    CaseSuiteSnapshot,
    ClarificationGap,
    HistoryRecord,
    HistoryRecordData,
    HistoryStage,
    StructuredSummary,
    TaskInputSnapshot,
    TestDesignSnapshot,
)

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
                record = self._parse_record(raw)
                if record:
                    records.append(record)
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
            return self._parse_record(raw)
        except Exception:
            return None

    def delete_record(self, record_id: str) -> bool:
        path = self._record_path(record_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def _parse_record(self, raw: dict) -> HistoryRecord | None:
        try:
            return HistoryRecord(**raw)
        except Exception:
            return self._convert_legacy_record(raw)

    def _convert_legacy_record(self, raw: dict) -> HistoryRecord | None:
        data = raw.get("data") or {}
        analysis = data.get("analysis") or {}
        review_result = data.get("reviewResult") or {}
        generation = data.get("generation") or {}
        integration_result = data.get("integrationResult") or {}

        if not analysis:
            return None

        summary = StructuredSummary(**(analysis.get("summary") or {}))
        test_design = TestDesignSnapshot(
            summary=summary,
            clarification_questions=analysis.get("clarification_questions") or [],
            clarification_answers=[],
            missing_fields=[ClarificationGap(**item) for item in analysis.get("missing_fields") or []],
            resolved_fields=analysis.get("resolved_fields") or [],
            remaining_risks=analysis.get("remaining_risks") or [],
            functions=analysis.get("functions") or [],
            flows=analysis.get("flows") or [],
            module_segments=analysis.get("module_segments") or {},
            coverage_dimensions=analysis.get("coverage_dimensions") or [],
            test_points=analysis.get("test_points") or [],
            reviewed_test_points=review_result.get("reviewed_test_points") or [],
            review_notes=review_result.get("review_notes") or [],
        )

        case_suite = None
        if generation:
            case_suite = CaseSuiteSnapshot(
                cases=generation.get("cases") or [],
                integration_tests=(generation.get("integration_tests") or integration_result.get("integration_tests") or []),
                regression_suites=generation.get("regression_suites") or [],
                validation_issues=generation.get("validation_issues") or [],
            )

        stage = HistoryStage.SUMMARY
        if case_suite:
            stage = HistoryStage.CASE_SUITE
        elif test_design.test_points or test_design.reviewed_test_points:
            stage = HistoryStage.TEST_DESIGN

        return HistoryRecord(
            id=raw.get("id", ""),
            title=raw.get("title", summary.title or "未命名任务"),
            platform=raw.get("platform", "web"),
            project=raw.get("project", ""),
            stage=raw.get("stage", stage),
            cases_count=raw.get("cases_count", len(case_suite.cases) if case_suite else 0),
            integration_count=raw.get("integration_count", len(case_suite.integration_tests) if case_suite else 0),
            timestamp=raw.get("timestamp", ""),
            data=HistoryRecordData(
                task_input=TaskInputSnapshot(
                    requirement_text="",
                    actors=[],
                    preconditions=[],
                    business_rules=[],
                ),
                test_design=test_design,
                case_suite=case_suite,
            ),
        )
