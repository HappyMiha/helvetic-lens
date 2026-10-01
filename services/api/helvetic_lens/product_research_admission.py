"""One shared account allowance for owned dossiers, never for research steps."""
from sqlalchemy import func, select

from .models import User
from .product_api import fail, iso
from .product_models import DossierAllowance, DossierAllowanceSlot, DossierLimitRequest

CONTRACT = "dossier-admission/v1"
LIMIT = 3


def request_payload(row):
    return {"id": row.id, "requested_limit": row.requested_limit, "reason": row.reason,
        "status": row.status, "revision": row.revision, "approved_limit": row.approved_limit,
        "created_at": iso(row.created_at), "decided_at": iso(row.decided_at) if row.decided_at else None, "mail_state": row.mail_state}


def state(session, user_id, product=None):
    allowance = session.get(DossierAllowance, user_id)
    limit = allowance.limit if allowance else LIMIT
    used = session.scalar(select(func.count()).select_from(DossierAllowanceSlot).where(DossierAllowanceSlot.user_id == user_id))
    latest = session.scalar(select(DossierLimitRequest).where(DossierLimitRequest.user_id == user_id)
        .order_by(DossierLimitRequest.created_at.desc(), DossierLimitRequest.id.desc()).limit(1))
    return {"contract": CONTRACT, "limit": limit, "used": used, "remaining": max(0, limit - used),
        "revision": allowance.revision if allowance else 1, "scope": "account", "continuations_included": True,
        "message": "Your dossier allowance is shared by Legal and Pharma. Research within your dossiers has no internal execution budget.",
        "latest_request": request_payload(latest) if latest else None}


def admit_dossier(session, user_id, dossier_id):
    # The account row serializes creation across products, workspaces and workers.
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if session.get(DossierAllowanceSlot, dossier_id):
        return
    if state(session, user_id)["remaining"] == 0:
        fail("Your dossier limit has been reached. Request a higher limit to create another dossier; your existing research can continue.",
            429, "dossier_allowance_exhausted")
    session.add(DossierAllowanceSlot(user_id=user_id, dossier_id=dossier_id))
    session.flush()


def policy(dossier_id):
    return {"contract": CONTRACT, "dossier_id": dossier_id}


def unmetered(run):
    data = run.research_state or {}
    return data.get("admission", {}).get("contract") == CONTRACT or data.get("mission", {}).get("contract") == "research-mission/v1"
