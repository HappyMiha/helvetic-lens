"""User-visible digest limits must describe saved selection, including in email."""

from datetime import timedelta

import pytest

from helvetic_lens import digests
from helvetic_lens.config import Settings
from helvetic_lens.db import utcnow
from helvetic_lens.models import DigestDelivery, DigestPreference, User


def make_summary(count=6, event_overflow=False):
    end = utcnow()
    impact = {"severity": "high", "law_id": "law", "law_title": "Law <test>", "potential_effect": "Saved effect",
              "suggested_next_step": "Review", "links": {"relation_evidence": "/evidence/test-only"}}
    group = {"event_id": "event", "title": "Test <event>", "source": "test", "detected_at": (end - timedelta(seconds=1)).isoformat(),
             "items": [dict(impact, law_id=str(i)) for i in range(count)] + [dict(impact, severity="low")]}
    groups = [group] * (51 if event_overflow else 1)
    return digests.summarize_groups(groups, DigestPreference(sources=[], severities=["high"]), end - timedelta(days=1), end)


@pytest.mark.parametrize("count,limited", [(0, False), (5, False), (6, True)])
def test_law_coverage_counts_only_eligible_laws(count, limited):
    summary = make_summary(count)
    if not count:
        assert summary == {"events": [], "truncated": False}
        return
    event = summary["events"][0]
    assert event["impact_count"] == count and event["impacts_truncated"] is limited
    assert len(event["impacts"]) == min(count, 5)
    assert all(item["evidence"] == "/evidence/test-only" for item in event["impacts"])


@pytest.mark.parametrize("locale", list(digests._MESSAGES))
@pytest.mark.parametrize("count,event_overflow", [(5, False), (5, True), (6, False), (6, True)])
def test_email_text_and_html_expose_event_and_law_limits(locale, count, event_overflow):
    summary = make_summary(count, event_overflow)
    delivery = DigestDelivery(id="test", preference_id="test", summary=summary)
    settings = Settings(_env_file=None, public_base_url="https://portal.example")
    user = User(email="test@example.ch", locale=locale, name="Test", password_hash="test")
    _, text, html = digests.render_message(settings, delivery, user)
    event_notice = digests._MESSAGES[locale]["event_limit"]
    law_notice = digests._MESSAGES[locale]["more_laws"].format(shown=5, total=count)
    assert (event_notice in text) is event_overflow
    assert (event_notice in html) is event_overflow
    assert (law_notice in text) is (count > 5)
    assert (law_notice in html) is (count > 5)
    assert "https://portal.example/impact" in text and 'href="https://portal.example/impact"' in html
    assert "Test &lt;event&gt;" in html and "Law &lt;test&gt;" in html
    assert "{shown}" not in text and "{total}" not in html


def test_legacy_email_summary_without_law_counts_still_renders():
    summary = make_summary(5)
    for item in summary["events"]:
        item.pop("impact_count")
        item.pop("impacts_truncated")
    _, text, html = digests.render_message(Settings(_env_file=None), DigestDelivery(id="test", preference_id="test", summary=summary),
                                         User(email="test@example.ch", locale="en-CH", password_hash="test", name="Test"))
    assert "5 of" not in text and "Showing" not in html
