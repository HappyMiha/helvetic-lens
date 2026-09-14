"""Two opposite-order native review batches must have exactly one atomic winner."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from helvetic_lens import monitoring_batch_review as batch
from helvetic_lens.business_item_models import BusinessItemWorkEvent
from helvetic_lens.config import DomainError, Settings
from helvetic_lens.db import Database
from helvetic_lens.models import Organization, OrganizationMembership, User
from helvetic_lens.monitoring_evidence_ask import Record
from helvetic_lens.tender_models import TenderDossier
from test_business_monitor_sharing import configure
from test_tender_matching import NOW
from test_tender_repository import create, ingest, publication


def check(db):
    with db.session(include_all_organizations=True) as session:
        session.add(Organization(id="org-a", name="Synthetic", slug="synthetic"))
        session.add_all([User(id=user, name=user, email=f"{user}@example.invalid", password_hash="unused") for user in ("owner", "peer")])
        session.flush()
        session.add_all([OrganizationMembership(organization_id="org-a", user_id=user, role="organization_admin") for user in ("owner", "peer")])
        session.commit()
    records = []
    for number in range(2):
        monitor = create(db, active=True, key=f"batch-{number}")
        item = ingest(db, monitor, publication())[0]
        configure(db, "tenders", monitor["id"], version=1, now=NOW)
        records.append(Record("tenders", monitor["id"], item))
    settings = Settings(_env_file=None, tender_watch_enabled=True)
    gate = Barrier(2)

    def writer(user):
        selected = records if user == "owner" else list(reversed(records))
        with db.session() as session:
            preview = batch.preview(session, settings, user, selected, now=NOW, locale="en-CH")
        choices = [(record, row["binding"], "no_bid") for record, row in zip(selected, preview["items"], strict=True)]
        gate.wait(timeout=15)
        with db.session() as session:
            try:
                result = batch.apply(session, settings, user, choices, now=NOW, locale="en-CH")
                session.commit()
                return result["count"]
            except DomainError as error:
                session.rollback()
                assert error.status == 409, error.code
                return 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, user) for user in ("owner", "peer")]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(results) == [0, 2], results
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(BusinessItemWorkEvent)) == 2
        assert set(session.scalars(select(TenderDossier.decision))) == {"no_bid"}
        actors = set(session.scalars(select(BusinessItemWorkEvent.actor_user_id)))
        assert len(actors) == 1, actors
    print("PostgreSQL: opposite-order two-item batches have one complete winner, one conflict, no partial audit or deadlock.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"} or url.database != "helvetic_lens_batch_check":
        parser.error("Use only an empty localhost helvetic_lens_batch_check database.")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                parser.error("Refusing to modify a database containing tables.")
    finally:
        engine.dispose()
    with TemporaryDirectory(prefix="helvetic-batch-check-") as artifacts:
        db = Database(Settings(_env_file=None, database_url=args.database_url, data_dir=Path(artifacts)), organization_id="org-a")
        try:
            db.migrate()
            check(db)
        finally:
            db.engine.dispose()
