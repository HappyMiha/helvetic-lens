"""Linux subprocess fixture for real supervisor/group shutdown; no Celery IO."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helvetic_lens.worker_supervisor import supervise  # noqa: E402


def wait_for(predicate, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Isolated process condition did not complete")


def live(pid):
    status = Path(f"/proc/{pid}/stat")
    if not status.exists():
        return False
    return status.read_text().split(") ", 1)[1].split()[0] != "Z"


def worker(root, name, scenario):
    if scenario == "ignore":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (root / name).write_text(json.dumps({"pid": os.getpid(), "grandchild": grandchild.pid,
        "pool": os.getenv("DATABASE_POOL_SIZE"), "overflow": os.getenv("DATABASE_MAX_OVERFLOW")}))
    while not (root / ("crash-" + name)).exists():
        time.sleep(0.02)
    raise SystemExit(3)


def parent(root, scenario):
    commands = [(name, [sys.executable, "-B", __file__, "worker", str(root), name, scenario])
        for name in ("cpu", "control", "sources", "bulk", "projection", "delivery")]
    raise SystemExit(supervise(commands, grace_seconds=0.4))


def probe(scenario):
    with tempfile.TemporaryDirectory(prefix="hl-supervisor-") as directory:
        root = Path(directory)
        process = subprocess.Popen([sys.executable, "-B", __file__, "parent", str(root), scenario],
            start_new_session=True, env={**os.environ, "DATABASE_POOL_SIZE": "4", "DATABASE_MAX_OVERFLOW": "2"})
        observed = []
        try:
            names = ("cpu", "control", "sources", "bulk", "projection", "delivery")
            wait_for(lambda: all((root / name).exists() and (root / name).stat().st_size for name in names))
            observed = [json.loads((root / name).read_text()) for name in names]
            assert all(live(row["pid"]) and live(row["grandchild"]) for row in observed)
            assert observed[0]["pool"] == "4" and observed[0]["overflow"] == "2"
            assert all(row["pool"] == "2" and row["overflow"] == "0" for row in observed[1:])
            if scenario == "crash":
                (root / "crash-control").touch()
            else:
                process.terminate()
            assert process.wait(timeout=8) == (1 if scenario == "crash" else 0)
            wait_for(lambda: all(not live(row["pid"]) and not live(row["grandchild"]) for row in observed))
            print(json.dumps({"scenario": scenario, "parents_stopped": 6, "grandchildren_stopped": 6,
                "database_budgets_preserved": True}))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            # Only PIDs recorded from this experiment; never production services.
            for row in observed:
                for key in ("pid", "grandchild"):
                    try:
                        os.kill(row[key], signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    if sys.argv[1] == "worker":
        worker(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "parent":
        parent(Path(sys.argv[2]), sys.argv[3])
    else:
        probe(sys.argv[1])
