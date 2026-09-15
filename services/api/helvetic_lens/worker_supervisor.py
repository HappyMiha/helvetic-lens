"""Independent CPU consumers with one deployment-managed container lifecycle."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from threading import Event

from .monitoring_queues import CPU_WORKERS


def worker_commands():
    return [(name, [sys.executable, "-m", "celery", "-A", "helvetic_lens.celery_app:celery_app",
        "worker", "--loglevel=INFO", "--hostname", f"{name}@{socket.gethostname()}",
        "-Q", queues, f"--concurrency={concurrency}"]) for name, queues, concurrency in CPU_WORKERS]


def _kill_group(process):
    # Each child is launched as its own POSIX session. This includes prefork
    # children left behind after an unexpected Celery parent exit.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def supervise(commands, *, grace_seconds=120):
    """Linux-container entry point; any lost consumer fails the entire group."""
    if os.name != "posix":
        raise RuntimeError("The CPU worker supervisor runs inside the Linux container")
    stop, processes = Event(), []
    handlers = {kind: signal.getsignal(kind) for kind in (signal.SIGTERM, signal.SIGINT)}
    for kind in handlers:
        signal.signal(kind, lambda *_: stop.set())
    result = 0
    try:
        for name, command in commands:
            if stop.is_set():
                break
            environment = os.environ.copy()
            if name != "cpu":
                environment.update(DATABASE_POOL_SIZE="2", DATABASE_MAX_OVERFLOW="0")
            process = subprocess.Popen(command, env=environment, start_new_session=True)
            processes.append((name, process))
        while not stop.wait(0.2):
            for name, process in processes:
                if process.poll() is not None:
                    print(f"CPU consumer exited unexpectedly: {name}", file=sys.stderr, flush=True)
                    result = 1
                    stop.set()
                    break
    finally:
        # Warm-stop every parent together; don't serially consume the grace
        # period once per worker. Docker's stop grace exceeds this deadline.
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + grace_seconds
        while any(process.poll() is None for _, process in processes) and time.monotonic() < deadline:
            time.sleep(0.05)
        for _, process in processes:
            _kill_group(process)
        for _, process in processes:
            process.wait(timeout=10)
        for kind, handler in handlers.items():
            signal.signal(kind, handler)
    return result


def healthy():
    from .celery_app import celery_app
    names = [f"{name}@{socket.gethostname()}" for name, _, _ in CPU_WORKERS]
    try:
        replies = celery_app.control.inspect(destination=names, timeout=3).ping() or {}
        return all(replies.get(name, {}).get("ok") == "pong" for name in names)
    except Exception:
        # Health output must never echo a broker URL or credentials.
        return False


def main():
    if sys.argv[1:] == ["--healthcheck"]:
        return 0 if healthy() else 1
    if sys.argv[1:]:
        raise SystemExit("Only --healthcheck is supported")
    return supervise(worker_commands())


if __name__ == "__main__":
    raise SystemExit(main())
