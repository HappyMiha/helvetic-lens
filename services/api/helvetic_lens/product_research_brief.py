"""Printable reading from the same authorized projection as the dossier overview."""
from html import escape
from urllib.parse import urlsplit


def esc(value):
    return escape(str(value or ""), quote=True)


def paragraph(value, *, css=""):
    return f'<p class="{css}">{esc(value)}</p>' if value else ""


def items(title, values):
    return (f'<h4>{esc(title)}</h4><ul>' + ''.join(f'<li>{esc(value)}</li>' for value in values)
            + '</ul>') if values else ""


def citation(ref, sources):
    source = sources.get(ref.get("source_id"))
    if source is None:
        return '<p>Supporting passage unavailable.</p>'
    url = source.get("url", "")
    parts = urlsplit(url)
    link = (f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(url)}</a>'
            if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password else "")
    role = {"counterevidence": "Counterevidence", "context": "Context"}.get(ref.get("role"), "Supporting passage")
    return (f'<div class="research-citation"><p class="meta">{esc(source.get("title") or "Source")} · {role}</p>'
            f'<blockquote>{esc(ref.get("quote"))}</blockquote>{paragraph(ref.get("locator"), css="meta")}'
            f'{link}{paragraph(source.get("captured_at"), css="meta")}</div>')


def reading(state):
    """Return only selected reader fields; never serialize a stored research state."""
    mission = state.get("mission") or {}
    if state.get("status") == "evidence_changed" or mission.get("stage") == "evidence_changed":
        return ""
    sources = {source["id"]: source for source in state.get("sources", [])}
    for origin in (mission.get("knowledge") or {}).get("document_origins", []):
        for source in origin.get("sources", []):
            sources.setdefault(source["id"], source)
    answer = mission.get("answer")
    brief = state.get("briefing") or {}
    if not answer:
        answer = brief.get("assessment")
    if not answer and brief.get("findings"):
        answer = {"points": [{"statement": f["statement"], "basis": f.get("basis"), "evidence": [
            {**f, "role": "counterevidence" if f.get("basis") == "contradiction" else "support"}]
        } for f in brief["findings"]], "limitations": brief.get("uncertainties", [])}
    if not answer:
        return ""
    parts = ['<p class="meta">AI · evidence-based assessment · open to human review</p>']
    if not mission.get("answer"):
        parts.append('<p>Saved preliminary findings; the full research answer is not yet available.</p>')
    if mission.get("stop") == "answer_unavailable":
        parts.append('<p><b>Last saved answer.</b> The latest attempt has not replaced this earlier answer.</p>')
    verification = mission.get("verification") or {}
    pending = mission.get("stop") == "review_unavailable" and verification.get("status") == "partial"
    if pending:
        parts.append('<h4>Some checks are still pending</h4>' + paragraph(verification.get("basis")))
    elif answer.get("status") == "partial":
        parts.append('<p>This is a partial answer. Important gaps remain.</p>')
    if answer.get("status") == "not_found":
        parts.append('<p>No answer was established in the material read. This does not establish that no answer exists.</p>')
    points, conflicts = [], []
    for point in answer.get("points", []):
        target = conflicts if any(ref.get("role") == "counterevidence" for ref in point.get("evidence", [])) else points
        qualifier = '<p class="meta">AI · analogy, not a direct match</p>' if point.get("basis") == "analogy" else ""
        target.append('<section class="research-point">' + qualifier + paragraph(point["statement"])
                      + ''.join(citation(ref, sources) for ref in point.get("evidence", [])) + '</section>')
    parts.extend(points)
    if conflicts:
        parts.append('<h4>Where the evidence conflicts</h4>' + ''.join(conflicts))
    limitations = [gap for gap in answer.get("limitations", []) if not pending or gap != verification.get("basis")]
    parts.append(items('What we still do not know', limitations))
    incomplete = [doc for doc in mission.get("documents", []) if not doc.get("complete")]
    if incomplete:
        parts.append('<h4>Documents still requiring work</h4>')
        for doc in incomplete:
            detail = 'Read; analysis is incomplete.' if doc.get("read_complete") else 'Reading is incomplete.'
            if doc.get("page_count"):
                detail += f' {doc.get("pages_read", 0)} of {doc["page_count"]} pages processed.'
            parts.append(paragraph(f'{doc.get("title") or "Document"} — {detail}'))
            parts.append(paragraph(doc.get("error") or doc.get("unread_reason")))
    checks = mission.get("requested_sources") or []
    if checks:
        labels = {"matched_read": "Original identified, read and analysed", "not_identified": "Not identified in the material checked",
                  "acquisition_unavailable": "Could not retrieve the original", "reading_incomplete": "Reading is incomplete",
                  "analysis_incomplete": "Read; analysis is incomplete"}
        parts.append('<h4>Source checks</h4><p class="meta">Source checks are separate from gaps in the answer.</p>')
        for check in checks:
            origin = {"planner_interpretation": "Named in the research plan", "literal_request": "Named in your question",
                      "submitted_url": "Link from your question"}.get(check.get("origin"), "Source check")
            parts.append(paragraph(check.get("requested_source") or "Source"))
            parts.append(paragraph(f'{origin} · {labels.get(check.get("status"), "Status unavailable")}', css="meta"))
    return ''.join(parts)


def research_brief(session, dossier_id):
    # Caller has already checked authenticated, current dossier access. Use the
    # established payload for source-origin ACLs and all current evidence fences.
    from .product_exploration_api import latest
    from .product_investigations import payload

    run = latest(session, dossier_id)
    if run is None:
        return ""
    value = payload(session, run, include_retained=True)
    state = value.get("exploration") or {}
    parts = ['<section class="research-reading"><h2>Research answer</h2>']
    if value.get("evidence_unavailable") or state.get("status") == "evidence_changed" or (state.get("mission") or {}).get("stage") == "evidence_changed":
        return ''.join(parts) + '<p>The supporting evidence has changed or is no longer accessible. Open the dossier to review it.</p></section>'
    status = {"queued": "Research queued", "running": "Research in progress", "paused": "Research paused",
              "cancelled": "Research stopped", "failed": "Latest attempt did not finish", "completed": "Research saved"}.get(value["status"], "Research saved")
    parts.extend([paragraph(value["question"]), paragraph(f'{status} · Updated {value["updated_at"]}', css="meta")])
    current = reading(state)
    if current:
        parts.append(current)
    else:
        parts.append('<p>No new answer has been saved for this research yet.</p>')
    if not (state.get("mission") or {}).get("answer"):
        retained = state.get("retained_research")
        previous = reading(retained["exploration"]) if retained else ""
        if previous:
            parts.extend(['<section class="retained-answer"><h3>Earlier saved research</h3>',
                          '<p>This answer belongs to the earlier question below. The current research has not replaced it.</p>',
                          paragraph(retained["question"]), paragraph(f'Updated {retained["updated_at"]}', css="meta"),
                          previous, '</section>'])
    parts.append('</section>')
    return ''.join(parts)
