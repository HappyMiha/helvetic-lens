"""Real scoped page plans and reversible indexes, using synthetic decisions only."""

import base64
import json
from datetime import UTC, timedelta
from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, insert, inspect, select, text
from test_action_history_pages import prepare

from helvetic_lens.action_history import Cursor
from helvetic_lens.db import utcnow
from helvetic_lens.models import ActionDecision

INDEX = "ix_action_decision_scope_cursor"
MIGRATION = Path(__file__).resolve().parents[1] / "alembic/versions/d6c8e0173a94_action_history_seek.py"
COLUMNS = ["organization_id", "analysis_id", "comparison_id", "action_key", "created_at", "id"]


def change_index(service, direction):
    with service.db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            run_path(str(MIGRATION))[direction]()


def test_action_index_roundtrip_preserves_decisions_and_cursor(harness):
    client, _, service, _ = harness
    _, _, _, _, _, url = prepare(harness, 41)
    first = client.get(url).json()
    expected = client.get(url, params={"cursor": first["next_cursor"]}).json()
    with service.db.engine.connect() as connection:
        found = {index["name"]: index for index in inspect(connection).get_indexes("action_decisions")}
        assert found[INDEX]["column_names"] == COLUMNS
    change_index(service, "downgrade")
    with service.db.engine.connect() as connection:
        assert INDEX not in {index["name"] for index in inspect(connection).get_indexes("action_decisions")}
    assert client.get(url, params={"cursor": first["next_cursor"]}).json() == expected
    change_index(service, "upgrade")
    assert client.get(url, params={"cursor": first["next_cursor"]}).json() == expected


def nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


@pytest.mark.parametrize("tied", [False, True])
def test_deep_action_cursor_seeks_without_scanning_newer_decisions(harness, tied):
    client, _, service, model = harness
    _, comparison, report, action, calls, url = prepare(harness, 1)
    postgres = service.db.engine.dialect.name == "postgresql"
    count = 100_000 if postgres else 2_000
    boundary = count // 20
    with service.db.session() as session:
        template = dict(session.execute(select(ActionDecision.__table__)).mappings().one())
        stamp = template["created_at"].replace(tzinfo=UTC)
        for start in range(0, count, 1000):
            session.execute(
                insert(ActionDecision),
                [
                    {
                        **template,
                        "id": f"88000000-0000-0000-0000-{i:012}",
                        "created_at": stamp if tied else stamp + timedelta(seconds=i // 5),
                        "rationale": "Synthetic retained decision.",
                        "actor_label": f"Reviewer {i}",
                    }
                    for i in range(start, min(start + 1000, count))
                ],
            )
        session.commit()
    if postgres:
        with service.db.engine.begin() as connection:
            connection.execute(text("ANALYZE action_decisions"))
    position = Cursor(
        organization_id=service.organization_id,
        comparison_id=comparison["id"],
        analysis_id=report["id"],
        action_key=action,
        limit=20,
        as_of=utcnow(),
        at=stamp if tied else stamp + timedelta(seconds=boundary // 5),
        id=f"88000000-0000-0000-0000-{boundary:012}",
    )
    cursor = base64.urlsafe_b64encode(position.model_dump_json().encode()).decode().rstrip("=")
    queries = []

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "action_decisions" in statement:
            queries.append((statement, parameters))

    event.listen(service.db.engine, "before_cursor_execute", capture)
    try:
        response = client.get(url, params={"cursor": cursor})
    finally:
        event.remove(service.db.engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == count + 1
    assert [row["id"] for row in page["items"]] == [
        f"88000000-0000-0000-0000-{i:012}" for i in range(boundary - 1, boundary - 21, -1)
    ]
    assert len(queries) == 2  # Exact count and bounded payload, plus separate access lookup.
    assert len(model.calls) == calls
    if not postgres:
        return
    statement, parameters = next(query for query in queries if "LIMIT" in query[0])

    def explain():
        with service.db.engine.connect() as connection:
            return connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement,
                parameters,
            ).scalar_one()[0]

    # Measure this actual emitted page query before and after the new index.
    change_index(service, "downgrade")
    baseline = explain()
    change_index(service, "upgrade")
    indexed = explain()
    decision_nodes = [
        node for node in nodes(indexed["Plan"]) if node.get("Relation Name") == "action_decisions"
    ]
    assert len(decision_nodes) == 1
    scan = decision_nodes[0]
    # On distributed timestamps PostgreSQL can prefer its existing narrow time
    # index and sort just one small tie group. Do not force planner settings.
    # A large equal-time group must instead seek on both timestamp and ID.
    if tied:
        assert scan["Index Name"] == INDEX, indexed
        assert "ROW" in scan["Index Cond"] and "created_at" in scan["Index Cond"], indexed
    assert scan["Actual Rows"] * scan["Actual Loops"] <= (21 if tied else 26), indexed
    assert scan.get("Rows Removed by Filter", 0) <= (0 if tied else 5), indexed
    assert not any(node["Node Type"] == "Sort" for node in nodes(indexed["Plan"])), indexed
    print(
        "Action history deep-page plan: "
        + json.dumps(
            {
                "synthetic_decisions": count + 1,
                "equal_timestamps": tied,
                "newer_decisions_skipped": count - boundary,
                "baseline_ms": baseline["Execution Time"],
                "indexed_ms": indexed["Execution Time"],
                "baseline_decision_nodes": [
                    node
                    for node in nodes(baseline["Plan"])
                    if node.get("Relation Name") == "action_decisions"
                ],
                "indexed_decision_node": scan,
                "limit": 21,
                "exact_total_count_cost": "not bounded by page size",
            },
            default=str,
        )
    )
