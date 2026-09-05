"""Locate literal date/period mentions, without asserting their legal meaning.

This is deliberately not a deadline calculator or a negative date review. A date
in a proposal, historical reference or exception is still only a source mention.
"""

import re

METHOD = "date-mentions-v1"

# Full month names from the five supported source languages. Keep the literal
# source value: ambiguous numeric order, conditional dates and relative periods
# must not be silently resolved to an applicable calendar deadline.
MONTHS = (
    "january february march april may june july august september october november december "
    "januar februar märz mai juni juli oktober dezember "
    "janvier février mars avril juin juillet août septembre octobre novembre décembre "
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre dicembre "
    "schaner favrer mars avrigl matg zercladur fanadur avust settember october november december"
)
MONTH = "(?:" + "|".join(sorted(set(MONTHS.split()), key=lambda word: (-len(word), word))) + ")"
CALENDAR = re.compile(
    rf"(?<![\w./-])(?:"
    rf"\d{{4}}-\d{{2}}-\d{{2}}|"
    rf"\d{{1,2}}[./]\d{{1,2}}[./]\d{{4}}|"
    rf"\d{{1,2}}(?:\.|er|st|nd|rd|th)?\s+(?:(?:de|da)\s+)?{MONTH}\s+\d{{4}}|"
    rf"{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}"
    rf")(?!\w|[./-]\d)",
    re.IGNORECASE,
)
PERIOD = re.compile(
    r"(?<![\w./-])\d{1,4}(?:\s*(?:–|—|-|to|bis|à|a)\s*\d{1,4})?\s+"
    r"(?:business\s+days?|days?|weeks?|months?|years?|"
    r"Arbeitstag(?:e|en)?|Tag(?:e|en)?|Woche[n]?|Monat(?:e|en)?|Jahr(?:e|en)?|"
    r"jours?(?:\s+ouvrables?)?|semaines?|mois|ans?|années?|"
    r"giorni?(?:\s+lavorativi)?|settimane?|mesi|anni|"
    r"dis|emnas|mais|onns)(?!\w)",
    re.IGNORECASE,
)

LABELS = {
    "en-CH": ("Calendar date mentioned", "Period mentioned"),
    "de-CH": ("Erwähntes Kalenderdatum", "Erwähnter Zeitraum"),
    "fr-CH": ("Date mentionnée", "Période mentionnée"),
    "it-CH": ("Data menzionata", "Periodo menzionato"),
    "rm-CH": ("Data menziunada", "Perioda menziunada"),
}


def scan_date_mentions(evidence: list[dict], locale: str, *, limit: int = 8) -> tuple[list, dict]:
    """Scan the saved dossier, not model prose; retain both version sides.

    We count every match even after the display limit. Duplicate dossier rows
    are scanned once. No date field is established, even for a valid ISO token.
    Citations include the match even when it lies beyond a passage's preview.
    """
    labels = LABELS.get(locale, LABELS["en-CH"])
    entries = []
    seen = set()
    matched = 0
    for row in evidence:
        identity = (row["version_id"], row["passage_id"])
        if identity in seen:
            continue
        seen.add(identity)
        text = row["text"]  # Never _model_text: it may be shortened.
        matches = sorted(
            [(match, "other", labels[0]) for match in CALENDAR.finditer(text)]
            + [(match, "relative_period", labels[1]) for match in PERIOD.finditer(text)],
            key=lambda candidate: candidate[0].start(),
        )
        for match, kind, label in matches:
            matched += 1
            if len(entries) >= limit:
                continue
            quote = text[max(0, match.start() - 120) : match.end() + 120]
            entries.append(
                {
                    "kind": kind,
                    "label": label,
                    "date": None,
                    "mention": match.group(),
                    "version_side": row["side"],
                    "change_id": row.get("change_id"),
                    "status": "uncertain",
                    "evidence_grade": "needs_review",
                    "citations": [
                        {
                            "version_id": row["version_id"],
                            "passage_id": row["passage_id"],
                            "quote": quote,
                            "url": f"/evidence/{row['version_id']}?passage={row['passage_id']}",
                            "page": row.get("page"),
                        }
                    ],
                }
            )
    return entries, {
        "method": METHOD,
        "scope": "selected_material_evidence",
        "legal_meaning_status": "not_reviewed",
        "scanned_passages": len(seen),
        "detected_mentions": matched,
        "displayed_mentions": len(entries),
        "display_limited": matched > len(entries),
    }
