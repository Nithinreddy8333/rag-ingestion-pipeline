"""Dagster definitions: keep the index in step with the documents on a schedule.

    document_index  --(check: index is fresh and consistent)

Run from the repository root:  dagster dev -m orchestration.definitions
"""

from pathlib import Path

import dagster as dg

from rag_ingest.config import Settings
from rag_ingest.pipeline import pending_changes, run_ingest

ROOT = Path(__file__).resolve().parent.parent


def _settings() -> Settings:
    settings = Settings()
    for field in ("docs_dir", "state_path", "qdrant_path"):
        path = getattr(settings, field)
        if not path.is_absolute():
            setattr(settings, field, ROOT / path)
    return settings


@dg.asset(group_name="rag", description="Vector index of the documents folder, updated incrementally.")
def document_index() -> dg.MaterializeResult:
    stats = run_ingest(_settings())
    stats.pop("rejection_reasons")
    return dg.MaterializeResult(metadata=stats)


@dg.asset_check(asset=document_index, description="No pending changes, and index size matches the state.")
def index_is_fresh_and_consistent() -> dg.AssetCheckResult:
    report = pending_changes(_settings())
    last = report["last_run"] or {}
    consistent = last.get("points_in_store") == report["chunks"]
    return dg.AssetCheckResult(
        passed=bool(report["fresh"] and consistent),
        metadata={"documents": report["documents"], "chunks": report["chunks"],
                  "points_in_store": last.get("points_in_store", -1),
                  "pending": sum(len(v) for v in report["pending"].values())},
    )


refresh = dg.define_asset_job("refresh_index", selection=dg.AssetSelection.all())

defs = dg.Definitions(
    assets=[document_index],
    asset_checks=[index_is_fresh_and_consistent],
    jobs=[refresh],
    schedules=[dg.ScheduleDefinition(job=refresh, cron_schedule="15 * * * *")],
)
