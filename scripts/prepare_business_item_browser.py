"""Generate browser contracts through real native workflows in disposable SQLite."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "services/api/tests")]

from helvetic_lens import auction_repository, auction_workflow, business_item_work, tender_repository, trademark_repository, trademark_workflow  # noqa: E402
from helvetic_lens.config import Settings  # noqa: E402
from helvetic_lens.db import Database  # noqa: E402
from helvetic_lens.models import Organization, OrganizationMembership, User  # noqa: E402
from test_business_item_work import seed  # noqa: E402


def main():
    with TemporaryDirectory(prefix="helvetic-item-browser-") as directory:
        root = Path(directory)
        db = Database(Settings(_env_file=None, database_url=f"sqlite:///{(root / 'fixture.db').as_posix()}",
            data_dir=root / "data"), organization_id="org-a")
        try:
            db.migrate()
            with db.session(include_all_organizations=True) as session:
                session.add(Organization(id="org-a", name="Synthetic workspace", slug="synthetic-work"))
                session.add_all([User(id=user, name=user.title(), email=f"{user}@example.invalid", password_hash="fixture-unused") for user in ("owner", "peer", "viewer")])
                session.flush()
                session.add_all([OrganizationMembership(organization_id="org-a", user_id=user,
                    role="viewer" if user == "viewer" else "organization_admin") for user in ("owner", "peer", "viewer")])
                session.commit()
            fixtures = {}
            for domain in ("tenders", "ip", "auctions"):
                monitor, item, now, _ = seed(db, domain)
                with db.session() as session:
                    repository = {"tenders": tender_repository, "ip": trademark_repository, "auctions": auction_repository}[domain]
                    profile = repository.get_monitor(session, "owner", monitor)
                    if domain == "tenders":
                        detail = tender_repository.get_dossier(session, "owner", item, now=now)
                        page = tender_repository.list_dossiers(session, "owner", monitor, now=now)
                    elif domain == "ip":
                        page = trademark_workflow.list_candidates(session, "owner", monitor, now=now)
                        detail = page["items"][0]
                    else:
                        page = auction_workflow.list_items(session, "owner", monitor, now=now)
                        detail = page["items"][0]
                    fixtures[domain] = {"monitor": profile, "detail": detail, "page": page,
                        "work": business_item_work.read(session, "owner", domain, monitor, item, now=now)}
            destination = ROOT / ".tmp/business-item-browser-fixtures.json"
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(json.dumps(fixtures, default=str, ensure_ascii=False), encoding="utf-8")
            print("Three native source/workflow browser fixtures prepared in .tmp/business-item-browser-fixtures.json")
        finally:
            db.engine.dispose()


if __name__ == "__main__":
    main()
