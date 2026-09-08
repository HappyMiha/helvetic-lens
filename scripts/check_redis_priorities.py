"""Verify the real Celery/Kombu priority boundary on an EMPTY disposable Redis DB.

Publishes synthetic QA envelopes, consumes/acks them without executing any task.
Never connects to the application broker or invokes a worker/model/mail handler.
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

from redis import Redis

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))


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
    finally:
        celery_app.close()
    print("Redis priority gate passed: ten priority levels, two AI queues, interactive-before-background and equal-priority FIFO; 18 synthetic envelopes acked, no tasks executed.")


if __name__ == "__main__":
    main()
