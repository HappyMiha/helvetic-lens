"""Offline, script-free HTML packets. Source strings are never interpreted as markup."""

import json
from html import escape
from pathlib import Path

LABELS = json.loads(Path(__file__).with_name("trademark_export_labels.json").read_text(encoding="utf-8"))


def render(packet, locale):
    c, r = LABELS["packet"][locale], LABELS["review"][locale]

    def text(value):
        return escape(str(value), quote=True)

    def value(item):
        if item is None:
            return text(r["unknown"])
        if isinstance(item, dict):
            return "<dl>" + "".join(f"<dt>{text(r.get(k, k.replace('_', ' ')))}</dt><dd>{value(v)}</dd>" for k, v in item.items()) + "</dl>"
        if isinstance(item, (list, tuple)):
            return "<ul>" + "".join(f"<li>{value(v)}</li>" for v in item) + "</ul>" if item else text(r["unknown"])
        return text(item)

    def source(item, title):
        facts = dict(item["facts"])
        url = facts.pop("source_url")
        return f"<section><h2>{text(title)}</h2>{value(facts)}<p>{text(item['attribution'])}</p>" + (
            f'<p><a href="{text(url)}" rel="noopener noreferrer">{text(r["source"])}</a></p>'
            f'<details><summary>{text(c["provenance"])}</summary>{value({k:v for k,v in item.items() if k!="facts"})}</details></section>')

    review = r.get(packet["decision"], r["unknown"])
    state = r["needsReview"] if packet["needs_review"] else r["reviewed"]
    body = (f'<h1>{text(c["title"])}</h1><p>{text(c["warning"])}</p><p>{text(c["static"])}</p>'
        f'<p>{text(c["prepared"])}: {text(packet["prepared_at"])}</p><h2>{text(packet["portfolio_name"])}</h2>'
        f'<p>{text(c["profile"])}: {packet["profile_revision"]} · {text(c["candidateVersion"])}: {packet["candidate_sequence"]}</p>'
        f'<h2>{text(c["brand"])}</h2>{value(packet["brand"])}<p>{text(c["decision"])}: {text(review)} · {text(state)}</p>'
        + source(packet["source"], c["current"])
        + f'<h2>{text(c["assessment"])}</h2>{value(packet["assessment"])}<p>{text(r["classHelp"])}</p>')
    change = packet["selected_change"]
    if change:
        body += f'<h2>{text(c["selected"])}</h2><p>{text(change["detected_at"])} · {text(c["profile"])}: {change["profile_revision"]}</p>'
        body += value(change["change_codes"])
        if change["newer_available"]:
            body += f'<p>{text(r["newer"])}</p>'
        if change["before"]:
            body += source(change["before"], c["previous"])
        body += source(change["after"], r["at"]) + f'<h3>{text(c["assessment"])}</h3>{value(change["assessment"])}'
    body += (f'<h2>{text(c["deadline"])}</h2><p>{text(c["deadlineUnavailable"])}</p>'
        f'<p>{text(r["publication_date"])}: {value(packet["deadline_context"]["official_publication_date"])}</p>'
        f'<p>{text(c["warning"])}</p><details><summary>{text(c["provenance"])}</summary>'
        + value({k:packet[k] for k in ("schema", "monitor_id", "candidate_id", "evaluation_hash")}) + '</details>')
    return (f'<!doctype html><html lang="{locale}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        f'<title>{text(c["title"])}</title><style>body{{font:16px/1.55 system-ui,sans-serif;color:#172b39;background:white;max-width:850px;margin:auto;padding:24px;overflow-wrap:anywhere}}'
        'h1{font-size:1.7rem}h2{font-size:1.3rem;border-bottom:1px solid #9daab4;padding-top:18px}dt{font-weight:600}dd{margin:0 0 10px}dl dl{margin-left:16px}a{color:#005c8f}details{margin:16px 0}summary{cursor:pointer}@media print{body{padding:0}section{break-inside:auto}}</style>'
        '</head><body><main>' + body + '</main></body></html>')
