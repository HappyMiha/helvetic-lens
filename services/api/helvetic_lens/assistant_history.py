"""Read-only, principal-scoped metadata pages for personal Marvin conversations."""

import base64
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select

from .config import DomainError
from .db import utcnow
from .models import AssistantConversation as Conversation


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    organization: str = Field(min_length=1, max_length=64)
    principal: str = Field(min_length=1, max_length=80)
    limit: int = Field(ge=1, le=50)
    as_of: AwareDatetime
    at: AwareDatetime
    id: str = Field(min_length=1, max_length=36)


def iso(value: datetime) -> str:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def page(session, organization, principal, *, cursor="", limit=20):
    now, position = utcnow(), None
    if cursor:
        try:
            if len(cursor) > 2048:
                raise ValueError("Cursor too long")
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            position = Cursor.model_validate_json(raw)
            if (position.organization, position.principal, position.limit) != (organization, principal, limit):
                raise ValueError("Cursor scope changed")
            if position.at > position.as_of or position.as_of > now:
                raise ValueError("Invalid cursor date")
        except (ValueError, TypeError) as exc:
            raise DomainError("Refresh your personal conversation history.", 422, "invalid_history_page") from exc
    captured = position.as_of if position else now
    # Never load message, handoff or draft bodies into the list response or ORM.
    statement = select(
        Conversation.id, Conversation.route, Conversation.title,
        Conversation.entity_kind, Conversation.entity_id, Conversation.locale,
        Conversation.created_at, Conversation.updated_at,
        (func.length(Conversation.draft) > 0).label("has_draft"),
        func.coalesce(func.json_array_length(Conversation.messages_json), 0).label("message_count"),
        func.coalesce(func.json_array_length(Conversation.handoffs_json), 0).label("handoff_count"),
    ).where(
        Conversation.organization_id == organization,
        Conversation.principal_key == principal,
        Conversation.updated_at <= captured,
    )
    if position:
        statement = statement.where(or_(
            Conversation.updated_at < position.at,
            and_(Conversation.updated_at == position.at, Conversation.id < position.id),
        ))
    rows = list(session.execute(statement.order_by(
        Conversation.updated_at.desc(), Conversation.id.desc(),
    ).limit(limit + 1)).mappings())
    items = [
        {key: iso(value) if isinstance(value, datetime) else value for key, value in row.items()}
        for row in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        token = Cursor(organization=organization, principal=principal, limit=limit,
                       as_of=captured, at=datetime.fromisoformat(last["updated_at"]), id=last["id"])
        next_cursor = base64.urlsafe_b64encode(token.model_dump_json().encode()).decode().rstrip("=")
    return {"items": items, "next_cursor": next_cursor, "as_of": iso(captured), "visibility": "personal"}
