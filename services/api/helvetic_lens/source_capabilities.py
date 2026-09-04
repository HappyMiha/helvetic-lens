"""Versioned, user-visible contracts for every scheduled official source stream."""

from __future__ import annotations

from dataclasses import asdict, dataclass

CAPABILITY_SCHEMA_VERSION = "helvetic-lens.source-capability/v1"
CAPABILITY_CATALOG_REVISION = "2026-09-04.1"


@dataclass(frozen=True)
class CapabilityEvidence:
    fixture: bool = True
    incremental_overlap: bool = True
    deduplication: bool = True
    provenance: bool = True
    drift_detection: bool = True
    artifact_reopening: bool = True
    bounded_live_smoke: bool = False

    @property
    def promotion_ready(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True)
class SourceCapability:
    connector: str
    stream: str
    authority: str
    publisher: str
    jurisdiction: str
    document_kinds: tuple[str, ...]
    languages: tuple[str, ...]
    cadence: str
    incremental_cursor: str
    historical_window: str
    artifact_behavior: str
    provenance_behavior: str
    reuse_attribution: str
    known_gaps: tuple[str, ...]
    localized_copy: dict[str, dict[str, str]]
    last_verified_live_check: str | None
    evidence: CapabilityEvidence

    @property
    def catalogue_state(self) -> str:
        return "available" if self.evidence.promotion_ready else "partial"

    def serialize(self) -> dict:
        return {
            "schema_version": CAPABILITY_SCHEMA_VERSION,
            "catalogue_revision": CAPABILITY_CATALOG_REVISION,
            **asdict(self),
            "catalogue_state": self.catalogue_state,
            "evidence": {
                **asdict(self.evidence),
                "promotion_ready": self.evidence.promotion_ready,
            },
        }


_VERIFIED = CapabilityEvidence(bounded_live_smoke=True)
_FIXTURE_ONLY = CapabilityEvidence()

_LOCALIZED_COPY = {
    "fedlex": {
        "en-CH": {"summary": "Federal legislation and official publications from Fedlex.", "boundary": "Coverage follows the named feed or bounded catalogue cycle; a missing item never proves that nothing changed."},
        "de-CH": {"summary": "Bundesrecht und amtliche Veröffentlichungen aus Fedlex.", "boundary": "Die Abdeckung folgt dem genannten Feed oder einem begrenzten Kataloglauf; ein fehlender Eintrag beweist nie, dass sich nichts geändert hat."},
        "fr-CH": {"summary": "Droit fédéral et publications officielles de Fedlex.", "boundary": "La couverture suit le flux indiqué ou un cycle de catalogue limité; une absence ne prouve jamais qu’aucun changement n’a eu lieu."},
        "it-CH": {"summary": "Diritto federale e pubblicazioni ufficiali da Fedlex.", "boundary": "La copertura segue il feed indicato o un ciclo di catalogo limitato; un elemento assente non dimostra mai che non sia cambiato nulla."},
        "rm-CH": {"summary": "Dretg federal e publicaziuns uffizialas da Fedlex.", "boundary": "La cuvrida suonda il feed numnà u in ciclus da catalog limità; in element mancant na cumprova mai che nagut saja sa midà."},
    },
    "swiss-parliament": {
        "en-CH": {"summary": "Parliamentary affairs, initiatives, bills, and official notices.", "boundary": "Each stream has a stated discovery window; proposals and notices are not enacted law."},
        "de-CH": {"summary": "Parlamentsgeschäfte, Initiativen, Vorlagen und amtliche Mitteilungen.", "boundary": "Jeder Datenstrom hat ein ausgewiesenes Suchfenster; Vorlagen und Mitteilungen sind kein geltendes Recht."},
        "fr-CH": {"summary": "Objets parlementaires, initiatives, projets et communications officielles.", "boundary": "Chaque flux a une fenêtre de découverte déclarée; les projets et communications ne sont pas du droit en vigueur."},
        "it-CH": {"summary": "Oggetti parlamentari, iniziative, disegni e comunicati ufficiali.", "boundary": "Ogni flusso ha una finestra di scoperta dichiarata; proposte e comunicati non sono diritto vigente."},
        "rm-CH": {"summary": "Fatschentas parlamentaras, iniziativas, projects e communicaziuns uffizialas.", "boundary": "Mintga fluss ha ina fanestra da tschertga declerada; projects e communicaziuns n’èn betg dretg vertent."},
    },
    "federal-supreme-court": {
        "en-CH": {"summary": "Published decisions of the Swiss Federal Supreme Court.", "boundary": "The latest and reconciliation windows are bounded and do not constitute a complete historical court archive."},
        "de-CH": {"summary": "Veröffentlichte Entscheide des Schweizerischen Bundesgerichts.", "boundary": "Die neuesten und abgeglichenen Zeitfenster sind begrenzt und bilden kein vollständiges historisches Gerichtsarchiv."},
        "fr-CH": {"summary": "Arrêts publiés du Tribunal fédéral suisse.", "boundary": "Les fenêtres récentes et de rapprochement sont limitées et ne constituent pas des archives judiciaires historiques complètes."},
        "it-CH": {"summary": "Decisioni pubblicate del Tribunale federale svizzero.", "boundary": "Le finestre recenti e di riconciliazione sono limitate e non costituiscono un archivio giudiziario storico completo."},
        "rm-CH": {"summary": "Decisiuns publitgadas dal Tribunal federal svizzer.", "boundary": "Las fanestras actualas e da reconciliaziun èn limitadas e na furman betg in archiv giudizial istoric cumplet."},
    },
    "federal-criminal-court": {
        "en-CH": {"summary": "Latest published decisions of the Swiss Federal Criminal Court.", "boundary": "Only the official latest-decision list is covered; absence is not proof that no decision exists."},
        "de-CH": {"summary": "Neueste veröffentlichte Entscheide des Bundesstrafgerichts.", "boundary": "Erfasst wird nur die amtliche Liste der neuesten Entscheide; ein fehlender Eintrag beweist nicht, dass kein Entscheid besteht."},
        "fr-CH": {"summary": "Dernières décisions publiées du Tribunal pénal fédéral.", "boundary": "Seule la liste officielle des décisions récentes est couverte; une absence ne prouve pas qu’aucune décision n’existe."},
        "it-CH": {"summary": "Ultime decisioni pubblicate del Tribunale penale federale.", "boundary": "È coperto solo l’elenco ufficiale delle decisioni recenti; un’assenza non dimostra che non esista alcuna decisione."},
        "rm-CH": {"summary": "Ultimas decisiuns publitgadas dal Tribunal penal federal.", "boundary": "Mo la glista uffiziala da las decisiuns actualas è cuvrida; in element mancant na cumprova betg ch’i na dettia nagina decisiun."},
    },
    "federal-news": {
        "en-CH": {"summary": "Official federal news, policy, regulator, and consultation notices.", "boundary": "This is contextual official information with a bounded recent window, never enacted law."},
        "de-CH": {"summary": "Amtliche Bundesnachrichten sowie Politik-, Behörden- und Vernehmlassungsmitteilungen.", "boundary": "Dies sind amtliche Kontextinformationen aus einem begrenzten aktuellen Zeitfenster, niemals geltendes Recht."},
        "fr-CH": {"summary": "Actualités fédérales officielles et communications politiques, réglementaires et de consultation.", "boundary": "Il s’agit d’informations officielles contextuelles dans une fenêtre récente limitée, jamais de droit en vigueur."},
        "it-CH": {"summary": "Notizie federali ufficiali e comunicati politici, normativi e di consultazione.", "boundary": "Sono informazioni ufficiali contestuali in una finestra recente limitata, mai diritto vigente."},
        "rm-CH": {"summary": "Novitads federalas uffizialas e communicaziuns politicas, regulatoricas e da consultaziun.", "boundary": "Quai èn infurmaziuns uffizialas contextualas d’ina fanestra actuala limitada, mai dretg vertent."},
    },
    "finma-news": {
        "en-CH": {"summary": "Official FINMA news, guidance, enforcement, and sanctions notices.", "boundary": "This contextual RSS coverage is not a complete rulebook and is never represented as enacted law."},
        "de-CH": {"summary": "Amtliche FINMA-Nachrichten zu Aufsicht, Wegleitungen, Enforcement und Sanktionen.", "boundary": "Diese kontextbezogene RSS-Abdeckung ist kein vollständiges Regelwerk und wird nie als geltendes Recht dargestellt."},
        "fr-CH": {"summary": "Actualités officielles de la FINMA sur la surveillance, les orientations, l’enforcement et les sanctions.", "boundary": "Cette couverture RSS contextuelle n’est pas un recueil complet de règles et n’est jamais présentée comme du droit en vigueur."},
        "it-CH": {"summary": "Notizie ufficiali FINMA su vigilanza, orientamenti, enforcement e sanzioni.", "boundary": "Questa copertura RSS contestuale non è un corpus normativo completo e non viene mai presentata come diritto vigente."},
        "rm-CH": {"summary": "Novitads uffizialas da la FINMA davart surveglianza, directivas, enforcement e sancziuns.", "boundary": "Questa cuvrida RSS contextuala n’è betg ina collecziun cumpletta da reglas e na vegn mai preschentada sco dretg vertent."},
    },
}


def _cap(
    connector: str,
    stream: str,
    *,
    authority: str,
    publisher: str,
    kinds: tuple[str, ...],
    languages: tuple[str, ...],
    cadence: str,
    cursor: str,
    history: str,
    artifact: str,
    provenance: str,
    reuse: str,
    gaps: tuple[str, ...],
    live: bool,
) -> SourceCapability:
    return SourceCapability(
        connector=connector,
        stream=stream,
        authority=authority,
        publisher=publisher,
        jurisdiction="CH-federal",
        document_kinds=kinds,
        languages=languages,
        cadence=cadence,
        incremental_cursor=cursor,
        historical_window=history,
        artifact_behavior=artifact,
        provenance_behavior=provenance,
        reuse_attribution=reuse,
        known_gaps=gaps,
        localized_copy=_LOCALIZED_COPY[connector],
        last_verified_live_check="2026-09-03" if live else None,
        evidence=_VERIFIED if live else _FIXTURE_ONLY,
    )


_FEDLEX_COMMON = dict(
    authority="fedlex",
    publisher="Swiss Confederation — Fedlex",
    languages=("de", "fr", "it", "rm", "en"),
    artifact="Official HTML/PDF/XML is retained by digest and can be reopened from saved evidence.",
    provenance="ELI identity, source revision, canonical URL, content hash, retrieval time, and connector/schema versions are retained.",
    reuse="Swiss Confederation — Fedlex; retain the canonical official publication link and retrieval record.",
)
_PARLIAMENT_COMMON = dict(
    authority="swiss_parliament",
    publisher="Parliamentary Services of the Federal Assembly",
    languages=("de", "fr", "it", "en"),
    artifact="Official catalogue metadata and linked parliamentary documents are retained as immutable evidence.",
    provenance="Affair ID, official revision, canonical URL, artifact hash, retrieval time, and connector/schema versions are retained.",
    reuse="Parliamentary Services, Bern; Helvetic Lens is not an official publication.",
)


SOURCE_CAPABILITIES = (
    *(
        _cap(
            "fedlex",
            f"rss-{language}",
            kinds=("act", "ordinance", "federal_gazette_publication"),
            cadence="every 15 minutes",
            cursor="overlapping RSS publication watermark",
            history="new and changed items exposed by the official language feed; not a complete historical catalogue",
            gaps=(
                "Feed absence is not proof that no legal change exists.",
                "Romansh and English do not have equivalent scheduled RSS streams.",
            ),
            live=language == "de",
            **_FEDLEX_COMMON,
        )
        for language in ("de", "fr", "it")
    ),
    *(
        _cap(
            "fedlex",
            f"reconcile-{collection}",
            kinds=("act", "ordinance", "federal_gazette_publication"),
            cadence="daily",
            cursor="bounded JOLux/SPARQL keyset reconciliation",
            history="complete bounded cycle over the selected Fedlex collection, accumulated across runs",
            gaps=(
                "One run processes a bounded page and does not imply a complete cycle.",
                "Available expressions and formats vary by publication and language.",
            ),
            live=collection == "cc",
            **_FEDLEX_COMMON,
        )
        for collection in ("cc", "oc", "fga")
    ),
    _cap(
        "fedlex",
        "consultations",
        kinds=("consultation", "draft", "explanatory_report"),
        cadence="every 6 hours",
        cursor="complete bounded consultation keyset cycle",
        history="consultations exposed by the current official JOLux catalogue",
        gaps=(
            "A proposal is contextual information and is never represented as enacted law.",
            "No dated live-smoke record is checked into the repository yet.",
        ),
        live=False,
        **_FEDLEX_COMMON,
    ),
    _cap(
        "swiss-parliament",
        "recent",
        kinds=("parliamentary_business", "initiative", "bill"),
        cadence="hourly",
        cursor="recent-tail overlap by affair ID and source revision",
        history="bounded recent tail plus accumulated previously observed affairs",
        gaps=("Recent-tail absence is not proof that an affair does not exist.", "Romansh records are not supplied by this API."),
        live=True,
        **_PARLIAMENT_COMMON,
    ),
    _cap(
        "swiss-parliament",
        "active",
        kinds=("parliamentary_business", "initiative", "bill"),
        cadence="every 6 hours",
        cursor="known-active affair reconciliation",
        history="affairs already known to Helvetic Lens while they remain active",
        gaps=("This stream cannot discover an older affair that was never ingested.", "Romansh records are not supplied by this API."),
        live=False,
        **_PARLIAMENT_COMMON,
    ),
    _cap(
        "swiss-parliament",
        "catalogue",
        kinds=("parliamentary_business", "initiative", "bill"),
        cadence="daily",
        cursor="50-row ID-ordered complete catalogue keyset",
        history="complete official affair catalogue accumulated over bounded pages",
        gaps=("One run is one bounded page, not a completed historical backfill.", "Romansh records are not supplied by this API."),
        live=True,
        **_PARLIAMENT_COMMON,
    ),
    _cap(
        "swiss-parliament",
        "notices",
        kinds=("official_notice",),
        languages=("de", "fr", "it", "rm", "en"),
        cadence="every 30 minutes",
        cursor="SharePoint Modified/ID watermark with overlap",
        history="official Parliament pages observed after the retained watermark",
        gaps=("This is contextual authority information, not enacted law.", "No dated live-smoke record is checked into the repository yet."),
        live=False,
        **{key: value for key, value in _PARLIAMENT_COMMON.items() if key != "languages"},
    ),
    _cap(
        "federal-supreme-court",
        "latest",
        authority="federal_supreme_court",
        publisher="Swiss Federal Supreme Court",
        kinds=("court_decision",),
        languages=("de", "fr", "it"),
        cadence="hourly",
        cursor="five insertion-date overlapping official index",
        history="latest official decision index plus accumulated observations",
        artifact="Official decision HTML is retained by digest and can be reopened.",
        provenance="Aza identity, docket, decision/insertion dates, canonical URL, hash, and retrieval record are retained.",
        reuse="Swiss Federal Supreme Court; retain the canonical decision link.",
        gaps=("The latest index is not a complete historical catalogue.", "The public website sitemap does not cover the decision database."),
        live=True,
    ),
    _cap(
        "federal-supreme-court",
        "reconcile",
        authority="federal_supreme_court",
        publisher="Swiss Federal Supreme Court",
        kinds=("court_decision",),
        languages=("de", "fr", "it"),
        cadence="daily",
        cursor="current/previous-year insertion-date reconciliation",
        history="bounded current and previous calendar year; accumulated older evidence remains retained",
        artifact="Official decision HTML is retained by digest and can be reopened.",
        provenance="Aza identity, docket, decision/insertion dates, canonical URL, hash, and retrieval record are retained.",
        reuse="Swiss Federal Supreme Court; retain the canonical decision link.",
        gaps=("Coverage is limited to current and previous year per cycle.", "No dated live-smoke record for the reconcile stream is checked in."),
        live=False,
    ),
    _cap(
        "federal-criminal-court",
        "latest",
        authority="federal_criminal_court",
        publisher="Swiss Federal Criminal Court",
        kinds=("court_decision",),
        languages=("de", "fr", "it"),
        cadence="hourly",
        cursor="50-item official latest-list overlap",
        history="only decisions currently exposed by the official latest list, plus accumulated observations",
        artifact="The official linked decision PDF is retained by digest and can be reopened.",
        provenance="Official UUID, docket, decision date, canonical URL, PDF hash, and retrieval record are retained.",
        reuse="Swiss Federal Criminal Court; retain the official source link and court attribution.",
        gaps=("This is not a complete historical catalogue.", "Only the first 40 PDF pages are scanned for citation candidates."),
        live=True,
    ),
    *(
        _cap(
            "federal-news",
            f"news-{language}",
            authority="swiss_confederation",
            publisher="Swiss Confederation — News Service Bund",
            kinds=("official_notice", "consultation_notice", "policy_notice"),
            languages=(language,),
            cadence="every 30 minutes" if language in {"de", "fr", "it"} else "hourly",
            cursor="overlapping publication timestamp and bounded offset paging",
            history="bounded recent official search window plus accumulated observations",
            artifact="The canonical official HTML page is retained by digest and can be reopened.",
            provenance="Language-group ID, revision, publishers, topics, canonical URL, hash, and retrieval record are retained.",
            reuse="Swiss Confederation — News Service Bund; retain the official publication link.",
            gaps=("Context-only notice; never represented as enacted law.", "No dated live-smoke record is checked into the repository yet."),
            live=False,
        )
        for language in ("de", "fr", "it", "rm", "en")
    ),
    *(
        _cap(
            "finma-news",
            f"news-{language}",
            authority="finma",
            publisher="Swiss Financial Market Supervisory Authority FINMA",
            kinds=("official_notice", "guidance", "enforcement_notice", "sanctions_notice"),
            languages=(language,),
            cadence="hourly",
            cursor="official RSS publication watermark with a two-day overlap",
            history="items retained in the current official language RSS plus accumulated observations",
            artifact="The canonical official HTML page is retained by digest and can be reopened.",
            provenance="Official item URL, publication revision, language, content hash, and retrieval record are retained.",
            reuse="FINMA; retain the canonical official publication link and attribution.",
            gaps=("Context-only notice; never represented as enacted law.", "No dated live-smoke record is checked into the repository yet."),
            live=False,
        )
        for language in ("de", "fr", "it", "en")
    ),
)

SOURCE_CAPABILITY_INDEX = {
    (item.connector, item.stream): item for item in SOURCE_CAPABILITIES
}


def source_capability(connector: str, stream: str) -> SourceCapability | None:
    return SOURCE_CAPABILITY_INDEX.get((connector, stream))


def capability_catalogue() -> dict:
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "catalogue_revision": CAPABILITY_CATALOG_REVISION,
        "items": [item.serialize() for item in SOURCE_CAPABILITIES],
    }
