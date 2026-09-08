"""Bounded digest projections of current saved briefs; no generation or scheduling."""
from dataclasses import dataclass
from html import escape

from .config import DomainError
from .interest_assessment import ModelIdentity
from .interest_brief_reader import read

# Transactional labels, not model instructions. Native-language review remains a
# separate release gate. The model's saved prose is never translated on delivery.
COPY = {
    "en": ["Saved AI brief", "No current validated brief is available in your language. Open the event for evidence.",
           "Analysis pending; this digest does not wait or start a new request.", "Analysis failed; source evidence remains available.",
           "Saved analysis is no longer current.", "Why this is relevant", "Organization importance", "Suggested review",
           "Limits and uncertainty", "Three reasons are shown. Open the event for the complete saved brief.", "Evidence", "Saved",
           {"high": "High", "medium": "Medium", "low": "Low", "undetermined": "Not assessed"}],
    "de": ["Gespeicherte KI-Analyse", "Keine aktuelle geprüfte Analyse in Ihrer Sprache verfügbar. Öffnen Sie die Belege zum Ereignis.",
           "Analyse ausstehend; dieser Digest wartet nicht und startet keine neue Anfrage.", "Analyse fehlgeschlagen; Quellenbelege bleiben verfügbar.",
           "Die gespeicherte Analyse ist nicht mehr aktuell.", "Warum dies relevant ist", "Bedeutung für die Organisation", "Empfohlene Prüfung",
           "Grenzen und Unsicherheit", "Drei Gründe werden angezeigt. Öffnen Sie das Ereignis für die vollständige Analyse.", "Beleg", "Gespeichert",
           {"high": "Hoch", "medium": "Mittel", "low": "Niedrig", "undetermined": "Nicht bewertet"}],
    "fr": ["Analyse IA enregistrée", "Aucune analyse actuelle validée dans votre langue. Ouvrez l’événement pour consulter les preuves.",
           "Analyse en attente ; cette synthèse n’attend pas et ne lance aucune requête.", "Échec de l’analyse ; les preuves restent disponibles.",
           "L’analyse enregistrée n’est plus actuelle.", "Pourquoi cet élément est pertinent", "Importance pour l’organisation", "Examen suggéré",
           "Limites et incertitude", "Trois raisons sont affichées. Ouvrez l’événement pour l’analyse complète.", "Preuve", "Enregistrée",
           {"high": "Élevée", "medium": "Moyenne", "low": "Faible", "undetermined": "Non évaluée"}],
    "it": ["Analisi IA salvata", "Nessuna analisi attuale validata nella tua lingua. Apri l’evento per le prove.",
           "Analisi in attesa; questo riepilogo non attende né avvia nuove richieste.", "Analisi non riuscita; le prove restano disponibili.",
           "L’analisi salvata non è più attuale.", "Perché è pertinente", "Importanza per l’organizzazione", "Verifica suggerita",
           "Limiti e incertezza", "Sono mostrati tre motivi. Apri l’evento per l’analisi completa.", "Prova", "Salvata",
           {"high": "Alta", "medium": "Media", "low": "Bassa", "undetermined": "Non valutata"}],
    "rm": ["Analisa IA memorisada", "Naginas analisas actualas validatas en tia lingua. Avra l’eveniment per las cumprovas.",
           "Analisa pendenta; quest resum na spetga betg e na lantscha nagina dumonda.", "L’analisa n’è betg reussida; las cumprovas restan disponiblas.",
           "L’analisa memorisada n’è betg pli actuala.", "Pertge che quai è relevant", "Impurtanza per l’organisaziun", "Examinaziun recumandada",
           "Limits ed intschertezza", "Trais motivs vegnan mussads. Avra l’eveniment per l’analisa cumpletta.", "Cumprova", "Memorisada",
           {"high": "Auta", "medium": "Mesauna", "low": "Bassa", "undetermined": "Betg valitada"}],
}


@dataclass(frozen=True)
class BriefReadContext:
    organization_id: str
    configuration: str
    models: dict[str, ModelIdentity]


def attach(session, organization_id, summary, locale, *, context=None, configuration=None):
    # Context comes from the service's bounded runtime observation, never a job
    # payload or stored result. The current persisted configuration must still fit.
    model = (context.models.get(locale) if context and context.organization_id == organization_id
             and context.configuration == configuration else None)
    projected = []
    for event in summary["events"]:
        try:
            saved = read(session, organization_id, event["event_id"], locale=locale, model=model)
        except DomainError as error:
            if error.status != 404:
                raise
            # The caller's selection is not an authorization cache for AI prose.
            saved = {"status": "not_current", "locale": locale, "assessment_id": None, "saved_at": None}
        brief = {key: saved[key] for key in ("status", "locale", "assessment_id", "saved_at")}
        if saved["status"] == "available":
            result = saved["result"]
            reasons = [{**row, "name": saved["interest_names"][row["interest_id"]]}
                       for row in result["why_in_radar"][:3]]
            claims = [result["what_happened"], result["importance"], result["next_step"], *reasons]
            ids = {identity for claim in claims for identity in claim["evidence_ids"]}
            brief.update(what_happened=result["what_happened"], importance=result["importance"],
                next_step=result["next_step"], why_in_radar=reasons,
                more_reasons=len(result["why_in_radar"]) > len(reasons),
                uncertainty=result["uncertainty"], input_limitations=result["input_limitations"],
                evidence_links={key: value for key, value in saved["evidence_links"].items() if key in ids})
        projected.append({**event, "brief": brief})
    return {**summary, "events": projected}


def render(brief, locale, application_url):
    """Render only the validated, recipient-language projection, escaping all prose."""
    if not brief:
        return [], ""
    language = locale.split("-")[0]
    labels = COPY[language]
    lines, blocks = [labels[0]], [f"<h3>{escape(labels[0])}</h3>"]
    status = brief["status"] if brief.get("locale") == language else "not_scheduled"
    if status != "available":
        label = labels[{"pending": 2, "failed": 3, "stale": 4}.get(status, 1)]
        return [*lines, label], "".join([*blocks, f"<p>{escape(label)}</p>"])
    stamp = f'{labels[11]}: {brief["saved_at"]}'
    lines.append(stamp)
    blocks.append(f'<p>{escape(stamp)}</p>')
    def claim(value, heading=""):
        line = f'{heading}: {value["text"]}' if heading else value["text"]
        lines.append(line)
        blocks.append(f"<p>{escape(line)}</p>")
        for index, identity in enumerate(value["evidence_ids"], 1):
            url = application_url(brief["evidence_links"].get(identity))
            if url:
                label = f"{labels[10]} {index}"
                lines.append(f"{label}: {url}")
                blocks.append(f'<a href="{escape(url, quote=True)}">{escape(label)}</a> ')
    claim(brief["what_happened"])
    claim(brief["importance"], f'{labels[6]} — {labels[12][brief["importance"]["level"]]}')
    for reason in brief["why_in_radar"]:
        claim(reason, f'{labels[5]} — {reason["name"]}')
    if brief["more_reasons"]:
        lines.append(labels[9])
        blocks.append(f"<p>{escape(labels[9])}</p>")
    claim(brief["next_step"], labels[7])
    limit = f'{labels[8]}: {brief["uncertainty"]}'
    lines.extend([limit, *brief["input_limitations"]])
    blocks.append(f"<p>{escape(limit)}</p>")
    blocks.extend(f'<p lang="en">{escape(item)}</p>' for item in brief["input_limitations"])
    return lines, f'<section lang="{language}">' + "".join(blocks) + "</section>"
