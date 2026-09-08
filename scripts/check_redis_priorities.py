"""Verify the real Celery/Kombu priority boundary on an EMPTY disposable Redis DB.

Publishes synthetic QA envelopes, consumes/acks them without executing any task.
Never connects to the application broker or invokes a worker/model/mail handler.
"""
import argparse
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlsplit

from redis import Redis

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))


def durable_handoff(celery_app, send, queues):
    """Exercise actual SQL selection → broker → ack; never execute a task."""
    from helvetic_lens import jobs
    from helvetic_lens.config import Settings
    from helvetic_lens.db import Database, utcnow
    from helvetic_lens.models import Job, Organization, OutboxMessage
    from sqlalchemy import select

    with TemporaryDirectory(prefix="helvetic-fair-redis-") as directory:
        root = Path(directory)
        database = Database(Settings(_env_file=None, database_url="sqlite:///" + (root / "qa.db").as_posix(),
                                     data_dir=root / "artifacts"))
        database.migrate()
        now = utcnow()
        try:
            with database.session(include_all_organizations=True) as session:
                orgs = [Organization(name="Synthetic QA tenant", slug=f"fair-redis-{i}") for i in range(2)]
                session.add_all(orgs)
                session.flush()
                identities = []
                for index, org in enumerate([orgs[0], orgs[0], orgs[1]]):
                    row, _ = jobs.enqueue(session, organization_id=org.id, job_type="synthetic",
                        target_type="synthetic", target_id=str(index), idempotency_key=f"fair-{index}",
                        queue="ai_background" if index < 2 else "ai_interactive", priority=2 if index < 2 else 8)
                    # The question becomes eligible after the first background
                    # envelope is handed off; its competitor stays in the DB.
                    row.available_at = now + timedelta(seconds=1 if index == 2 else 0)
                    session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == row.id)).available_at = row.available_at
                    identities.append(row.id)
                session.commit()

            def dispatch(at):
                with patch.object(jobs, "utcnow", return_value=at), database.session(include_all_organizations=True) as session:
                    def publish(_topic, queue, body, priority):
                        send("helvetic_lens.qa_priority_only", queues[0 if queue == "ai_background" else 1], body, priority)
                    result = jobs.dispatch(session, publish)
                    session.commit()
                    return result["sent"]

            def consume(expected_priority):
                received = []
                def accept(body, message):
                    assert message.headers["task"] == "helvetic_lens.qa_priority_only"
                    assert body[0] == [] and set(body[1]) == {"job_id"}
                    assert message.properties["priority"] == expected_priority
                    received.append(body[1]["job_id"])
                    message.ack()
                with (celery_app.connection_for_read() as connection,
                      connection.Consumer(queues=[celery_app.amqp.queues[q] for q in queues],
                                          callbacks=[accept], accept=["json"], prefetch_count=1)):
                    connection.drain_events(timeout=5)
                with database.session(include_all_organizations=True) as session:
                    assert jobs.claim(session, received[0], "qa-claim-only") is not None
                    session.commit()
                return received[0]

            assert dispatch(now) == 1
            assert dispatch(now + timedelta(seconds=1)) == 0  # Still unclaimed.
            first = consume(7)  # Durable priority 2 → Redis priority 7.
            assert first in identities[:2]
            assert dispatch(now + timedelta(seconds=1)) == 1
            assert consume(1) == identities[2]  # New question overtakes DB backlog.
            assert dispatch(now + timedelta(minutes=7)) == 1
            last = consume(0)  # Aging raises 2 → 9, then wire inversion → 0.
            assert last in identities[:2] and last != first
            with database.session(include_all_organizations=True) as session:
                assert session.get(Job, last).priority == 2
                assert session.get(Job, last).dispatch_sequence == 3
        finally:
            database.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", required=True)
    args = parser.parse_args()
    url = urlsplit(args.redis_url)
    if (url.scheme != "redis" or url.hostname != "127.0.0.1" or url.port != 56389
            or url.path != "/15" or url.username or url.password or url.query or url.fragment):
        parser.error("Use only redis://127.0.0.1:56389/15 on a disposable QA container.")
    with Redis.from_url(args.redis_url, socket_connect_timeout=3, socket_timeout=3) as client:
        if client.dbsize() != 0:
            parser.error("Refusing a nonempty Redis database; create a fresh QA container.")

    from helvetic_lens.celery_app import _send, celery_app
    celery_app.conf.update(broker_url=args.redis_url, broker_connection_timeout=3)
    seen = []
    queues = ["helvetic-qa-ai-background", "helvetic-qa-ai-interactive"]

    def accept(body, message):
        # Celery protocol v2: positional arguments, kwargs, embedded metadata.
        assert body[0] == [] and set(body[1]) == {"job_id"}, body
        assert message.headers["task"] == "helvetic_lens.qa_priority_only"
        seen.append(body[1]["job_id"])
        message.ack()

    def scenario(items, expected):
        seen.clear()
        for identity, priority, queue in items:
            _send("helvetic_lens.qa_priority_only", queue, {"job_id": identity}, priority)
        with celery_app.connection_for_read() as connection:
            active = [celery_app.amqp.queues[queue] for queue in dict.fromkeys(row[2] for row in items)]
            with connection.Consumer(queues=active, callbacks=[accept], accept=["json"], prefetch_count=1):
                for _ in items:
                    connection.drain_events(timeout=5)
        assert seen == expected, {"expected": expected, "received": seen}

    try:
        # Our persistent convention is high number = important. The real Redis
        # transport reads low numbers first, so this requires the adapter.
        scenario([(f"level-{n}", n, queues[0]) for n in range(10)],
                 [f"level-{n}" for n in reversed(range(10))])
        scenario([("brief-old", 2, queues[0]), ("admission", 1, queues[0]),
                  ("ask", 8, queues[1]), ("analysis", 5, queues[1]),
                  ("brief-new", 2, queues[0])],
                 ["ask", "analysis", "brief-old", "brief-new", "admission"])
        scenario([(f"fifo-{n}", 2, queues[0]) for n in range(3)],
                 [f"fifo-{n}" for n in range(3)])
        durable_handoff(celery_app, _send, queues)
    finally:
        celery_app.close()
    print("Redis priority gate passed: ten levels, two queues, FIFO and actual durable window/interactive overtaking/aging handoff; 21 synthetic envelopes acked, no tasks executed.")


if __name__ == "__main__":
    main()
