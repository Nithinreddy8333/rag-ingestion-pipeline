"""A synthetic internal handbook with known answers.

Every document is rendered from structured facts (owner, SLA, schedule, contacts ...), and
every eval question is generated from one of those facts. So for each question we know
exactly which document and which section hold the answer, which is what makes retrieval
scoring exact. Questions are phrased differently from the documents on purpose.

`mutate` simulates a week of edits (changed, deleted and new documents) for testing
incremental ingestion.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SERVICES = [
    "orders-cdc", "billing-export", "clickstream-sessionizer", "inventory-snapshot",
    "fraud-features", "customer-360", "pricing-sync", "shipment-tracker", "returns-ledger",
    "search-indexer", "email-events", "loyalty-points", "tax-calculator", "catalog-enrichment",
    "payments-reconciler", "ad-attribution", "churn-scores", "warehouse-loader",
    "support-tickets-etl", "geo-lookup", "currency-rates", "consent-registry",
    "recommendation-batch", "audit-archiver",
]
TEAMS = ["Atlas", "Borealis", "Cobalt", "Dynamo", "Ember", "Fjord", "Garnet", "Helix"]
PEOPLE = ["Priya Nair", "Tomas Reyes", "Mei Tanaka", "Jonas Weber", "Amara Okoye", "Lena Brandt",
          "Rahul Menon", "Sofia Marin", "Kenji Sato", "Ines Duarte", "Omar Haddad", "Clara Voss"]
STORES = ["Snowflake", "BigQuery", "Postgres", "Delta Lake on S3", "Redshift", "Iceberg on GCS"]
ENGINES = ["Spark", "dbt", "Flink", "Airflow with Python operators", "Kafka Streams", "Dagster assets"]
FAILURES = [
    ("the upstream schema changes without notice", "pause the job, regenerate the schema contract, and replay the dead-letter queue"),
    ("the source API starts rate limiting", "halve the batch size, enable the backoff flag, and resume from the last checkpoint"),
    ("the checkpoint store fills up", "expire checkpoints older than three days and restart the consumer group"),
    ("duplicate records appear after a retry", "run the idempotent merge with the dedupe key and compare row counts"),
    ("the warehouse credentials rotate", "pull the new secret from the vault path and redeploy the connection"),
    ("late-arriving events miss the window", "widen the watermark to two hours and backfill the affected partition"),
]
POLICIES = {
    "data-retention-policy": ("Data Retention Policy", [
        ("Raw zone", "Raw landing data is kept for {a} days and then moved to cold storage. Nothing in the raw zone is edited in place."),
        ("Curated zone", "Curated tables are kept for {b} months. Dropping a curated table needs sign-off from the owning team lead."),
        ("Legal holds", "A legal hold suspends every deletion job for the named dataset until the compliance group lifts it in writing."),
    ]),
    "access-request-policy": ("Access Request Policy", [
        ("Requesting access", "Access to a dataset is requested through the governance portal and must name a business reason and an end date."),
        ("Approval", "The dataset owner approves or declines within {a} business days. Access to restricted data also needs the privacy officer."),
        ("Reviews", "All grants are reviewed every {b} days, and anything unused for a full review period is revoked automatically."),
    ]),
    "incident-severity-guide": ("Incident Severity Guide", [
        ("Severity one", "Sev1 means customer-facing data is wrong or missing. The incident commander is paged at once and updates go out every {a} minutes."),
        ("Severity two", "Sev2 means an internal SLA is breached but no customer sees it. The owning team responds within {b} minutes during working hours."),
        ("Postmortems", "Every Sev1 and Sev2 gets a blameless postmortem within five working days, published in the reliability wiki."),
    ]),
    "pii-handling-standard": ("PII Handling Standard", [
        ("Classification", "Columns are tagged public, internal, confidential or restricted. Names, emails and phone numbers are confidential at minimum."),
        ("Masking", "Confidential columns are masked in every non-production environment using format-preserving hashing with a rotating salt."),
        ("Deletion requests", "An erasure request must be completed across all zones within {a} days, and the consent registry records the completion."),
    ]),
    "backfill-playbook": ("Backfill Playbook", [
        ("Before you start", "Announce the backfill in the data-changes channel and estimate the compute cost. Anything above {a} credits needs approval."),
        ("Running it", "Backfill one partition at a time, oldest first, with the write-audit-publish pattern so readers never see partial data."),
        ("Afterwards", "Reconcile row counts against the source, rerun downstream tests, and close the announcement thread with the totals."),
    ]),
    "naming-conventions": ("Naming Conventions", [
        ("Tables", "Staging tables start with stg_, facts with fct_ and dimensions with dim_. Names are snake_case and singular nouns are avoided."),
        ("Columns", "Timestamps end in _at, dates in _date and booleans start with is_ or has_. Money columns state the currency in a sibling column."),
        ("Jobs", "Job names follow domain-entity-action, for example orders-cdc or billing-export, and never include an environment name."),
    ]),
    "cost-tagging-rules": ("Cost Tagging Rules", [
        ("Required tags", "Every compute resource carries team, service and cost-center tags. Untagged resources are stopped after {a} hours."),
        ("Budgets", "Each team has a monthly budget, and an alert fires at {b} percent of it. Overruns are reviewed in the platform council."),
        ("Shared services", "Shared platform costs are split by query bytes scanned, measured monthly from the warehouse usage views."),
    ]),
    "oncall-handbook": ("On-call Handbook", [
        ("Rotations", "Rotations change on Mondays at 10:00 UTC. Each shift has a primary and a secondary, and swaps are recorded in the scheduler."),
        ("Paging", "A page must be acknowledged within {a} minutes. If the primary does not acknowledge, the secondary is paged automatically."),
        ("Handover", "The outgoing engineer writes a handover note listing open incidents, silenced alerts and risky deployments."),
    ]),
}
POLICY_QUESTIONS = {
    "data-retention-policy": [("Raw zone", "How long do we keep landing data before it goes to cold storage?"),
                              ("Legal holds", "What happens to deletion jobs when compliance freezes a dataset?")],
    "access-request-policy": [("Approval", "Who has to sign off before someone can read restricted data?"),
                              ("Reviews", "When are unused dataset permissions taken away?")],
    "incident-severity-guide": [("Severity one", "How often are updates sent when customers see wrong data?"),
                                ("Postmortems", "What is the deadline for writing up an outage review?")],
    "pii-handling-standard": [("Masking", "How are confidential fields protected in test environments?"),
                              ("Deletion requests", "How quickly must an erasure request be finished?")],
    "backfill-playbook": [("Before you start", "When does reprocessing history need cost approval?"),
                          ("Running it", "In what order should partitions be reprocessed?")],
    "naming-conventions": [("Columns", "How should boolean and timestamp fields be named?"),
                           ("Tables", "What prefix do fact and dimension tables use?")],
    "cost-tagging-rules": [("Required tags", "What happens to compute that has no team label?"),
                           ("Shared services", "How is the bill for common platform services divided?")],
    "oncall-handbook": [("Paging", "How fast does an alert need to be acknowledged?"),
                        ("Handover", "What should the engineer going off shift write down?")],
}


def _facts(rng: random.Random, name: str) -> dict:
    failures = rng.sample(FAILURES, 2)
    return {
        "name": name,
        "team": rng.choice(TEAMS),
        "owner": rng.choice(PEOPLE),
        "backup": rng.choice(PEOPLE),
        "engine": rng.choice(ENGINES),
        "store": rng.choice(STORES),
        "hour": rng.randrange(0, 24),
        "every": rng.choice([15, 30, 60, 180, 360, 1440]),
        "sla": rng.choice([1, 2, 4, 6, 12, 24]),
        "retention": rng.choice([30, 90, 180, 365, 730]),
        "channel": f"#{name.split('-')[0]}-alerts",
        "upstream": rng.choice([s for s in SERVICES if s != name]),
        "failures": failures,
        "phone": f"+1-555-{rng.randrange(100, 999)}-{rng.randrange(1000, 9999)}",
    }


def render_runbook(f: dict) -> str:
    cadence = "once a day" if f["every"] == 1440 else f"every {f['every']} minutes"
    lines = [
        f"# {f['name']} runbook", "",
        "## Overview", "",
        f"The {f['name']} pipeline is built with {f['engine']} and writes to {f['store']}. "
        f"It reads from {f['upstream']} and is maintained by team {f['team']}.", "",
        "## Schedule and SLA", "",
        f"The job runs {cadence}, with the first run of the day at {f['hour']:02d}:00 UTC. "
        f"Output must land within {f['sla']} hours of the source closing. "
        f"Output partitions are retained for {f['retention']} days.", "",
        "## Failure modes", "",
    ]
    for cause, fix in f["failures"]:
        lines += [f"If {cause}, {fix}.", ""]
    lines += [
        "## Restart procedure", "",
        f"Stop the {f['name']} job from the scheduler, confirm no task is still writing to "
        f"{f['store']}, then start it with the resume flag so it continues from the last "
        "committed offset. Never restart with a full refresh during business hours.", "",
        "## Contacts", "",
        f"The service owner is {f['owner']} and the backup is {f['backup']}. "
        f"Alerts go to {f['channel']}. For urgent issues call the on-call line at {f['phone']} "
        f"or write to {f['name']}-oncall@example.com.", "",
    ]
    return "\n".join(lines)


def runbook_questions(f: dict) -> list[dict]:
    n = f["name"]
    return [
        {"query": f"Who is responsible for {n} and where do its alarms get posted?", "heading": "Contacts"},
        {"query": f"What is the delivery deadline for {n} and how frequently does it execute?",
         "heading": "Schedule and SLA"},
        {"query": f"How do I safely bring {n} back up after stopping it?", "heading": "Restart procedure"},
        {"query": f"What should I do when {n} breaks because {f['failures'][0][0]}?",
         "heading": "Failure modes"},
        {"query": f"Which technology runs {n} and what does it depend on?", "heading": "Overview"},
    ]


def render_policy(slug: str, rng: random.Random) -> str:
    title, sections = POLICIES[slug]
    a, b = rng.choice([2, 3, 5, 7, 14, 30]), rng.choice([15, 30, 60, 80, 90])
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines += [f"## {heading}", "", body.format(a=a, b=b), ""]
    return "\n".join(lines)


def generate(seed: int = 7, services: list[str] | None = None) -> dict:
    """Return {'docs': {relative_path: markdown}, 'queries': [...]}."""
    rng = random.Random(seed)
    docs: dict[str, str] = {}
    queries: list[dict] = []
    for name in services or SERVICES:
        facts = _facts(rng, name)
        doc_id = f"runbooks/{name}.md"
        docs[doc_id] = render_runbook(facts)
        picked = rng.sample(runbook_questions(facts), 3)
        queries += [{**q, "doc_id": doc_id} for q in picked]
    for slug in POLICIES:
        doc_id = f"policies/{slug}.md"
        docs[doc_id] = render_policy(slug, rng)
        queries += [{"query": q, "doc_id": doc_id, "heading": h} for h, q in POLICY_QUESTIONS[slug]]
    for i, q in enumerate(queries):
        q["id"] = f"q{i:03d}"
    return {"docs": docs, "queries": queries}


def write(corpus: dict, docs_dir: Path, queries_path: Path | None = None) -> None:
    for rel, text in corpus["docs"].items():
        path = docs_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if queries_path:
        queries_path.parent.mkdir(parents=True, exist_ok=True)
        with queries_path.open("w", encoding="utf-8") as fh:
            for q in corpus["queries"]:
                fh.write(json.dumps(q) + "\n")


def mutate(docs_dir: Path, seed: int = 1, n_edit: int = 4, n_delete: int = 2, n_add: int = 2) -> dict:
    """Edit one section in some runbooks, delete some, add new ones. Returns what changed."""
    rng = random.Random(seed)
    runbooks = sorted((docs_dir / "runbooks").glob("*.md"))
    chosen = rng.sample(runbooks, n_edit + n_delete)
    edited, deleted, added = [], [], []
    for path in chosen[:n_edit]:
        text = path.read_text(encoding="utf-8")
        marker = "Output must land within "
        start = text.index(marker) + len(marker)
        end = text.index(" hours", start)
        new_sla = int(text[start:end]) + 1
        path.write_text(text[:start] + str(new_sla) + text[end:], encoding="utf-8")
        edited.append(str(path.relative_to(docs_dir)))
    for path in chosen[n_edit:]:
        path.unlink()
        deleted.append(str(path.relative_to(docs_dir)))
    for i in range(n_add):
        name = f"new-service-{seed}-{i}"
        path = docs_dir / "runbooks" / f"{name}.md"
        path.write_text(render_runbook(_facts(rng, name)), encoding="utf-8")
        added.append(str(path.relative_to(docs_dir)))
    return {"edited": edited, "deleted": deleted, "added": added}
