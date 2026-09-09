"""Explicit Basel-Stadt pilot scope, independent of the federal starter."""

PACK_ID = "basel-stadt-legislation"
ROOT_ID = "cantonal-pilots"
REVISION = "2026-09-09.1"


def localized(en, de, fr, it, rm):
    return dict(zip(("en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"), (en, de, fr, it, rm)))


NAME = localized("Basel-Stadt legislation · pilot", "Basel-Stadt Recht · Pilot",
                 "Droit de Bâle-Ville · pilote", "Diritto di Basilea Città · pilota", "Dretg da Basilea-Citad · pilot")
SCOPE = localized(
    "German texts and versions from the official Basel-Stadt legislation dataset, including its municipal entries. No court decisions, parliamentary business, complete Kantonsblatt or annex contents. The Kantonsblatt publication is authoritative.",
    "Deutsche Texte und Fassungen aus dem amtlichen Gesetzesdatensatz Basel-Stadt, einschliesslich seiner Gemeindeerlasse. Keine Gerichtsentscheide, Parlamentsgeschäfte, vollständige Kantonsblatt-Abdeckung oder Anhangsinhalte. Massgeblich ist die Publikation im Kantonsblatt.",
    "Textes et versions allemands du jeu officiel de Bâle-Ville, y compris ses actes communaux. Sans décisions judiciaires, objets parlementaires, couverture complète du Kantonsblatt ni contenu des annexes. La publication au Kantonsblatt fait foi.",
    "Testi e versioni tedeschi del dataset ufficiale di Basilea Città, inclusi gli atti comunali presenti. Esclusi decisioni giudiziarie, oggetti parlamentari, copertura completa del Kantonsblatt e contenuti degli allegati. Fa fede la pubblicazione nel Kantonsblatt.",
    "Texts e versiuns tudestgas dal dataset uffizial da Basilea-Citad, inclus ils relaschs communals cuntegnids. Senza decisiuns giudizialas, fatschentas parlamentaras, cuvrida cumpletta dal Kantonsblatt e cuntegns dals agiuntas. La publicaziun en il Kantonsblatt è decisiva.",
)
FIRST_DATA = localized(
    "Saved shared records are reused first. Scheduled pages collect the dataset gradually; an empty result or a completed page does not establish complete coverage. Newly detected historical versions are not new legal changes.",
    "Gespeicherte gemeinsame Einträge werden zuerst wiederverwendet. Geplante Seitenläufe erfassen den Datensatz schrittweise; leere Ergebnisse oder fertige Seiten belegen keine vollständige Abdeckung. Neu erkannte historische Fassungen sind keine neuen Rechtsänderungen.",
    "Les données partagées enregistrées sont réutilisées d’abord. La collecte planifiée avance par pages; un résultat vide ou une page terminée ne prouve pas une couverture complète. Une ancienne version nouvellement détectée n’est pas une nouvelle modification du droit.",
    "Si riutilizzano prima i dati condivisi salvati. La raccolta pianificata procede per pagine; risultati vuoti o pagine completate non provano la copertura completa. Una versione storica appena rilevata non è una nuova modifica normativa.",
    "Ils records communabels memorisads vegnan reutilisads l’emprim. La rimnada planisada avanza pagina per pagina; resultats vids u paginas terminadas na cumprovan betg ina cuvrida cumpletta. Versiuns istoricas chattadas da nov n’èn betg novas midadas dal dretg.",
)


PACKS = (
    dict(id=ROOT_ID, parent_id=None, position=100, name_json=NAME, description_json=SCOPE,
         expected_first_data_json=FIRST_DATA, filters_json={"children": [PACK_ID]}),
    dict(id=PACK_ID, parent_id=ROOT_ID, position=110, name_json=NAME, description_json=SCOPE,
         expected_first_data_json=FIRST_DATA,
         filters_json={"streams": [[PACK_ID, "starter-de"], [PACK_ID, "latest-de"], [PACK_ID, "catalogue-de"]],
                       "jurisdiction": "CH-BS", "canton": "BS", "pilot": True}),
)


def capabilities(capability_class, evidence_class):
    return tuple(capability_class(
        connector=PACK_ID, stream=stream, authority="basel_stadt", publisher="Zentraler Rechtsdienst / Open Data Basel-Stadt",
        jurisdiction="CH-BS", document_kinds=("act", "ordinance", "unclassified_document"), languages=("de",),
        cadence=cadence, incremental_cursor="Descending numeric version ID; repeated cycles observe corrections; interrupted pages retain their cursor.",
        historical_window=window,
        artifact_behavior="Publisher HTML field retained by hash; exact OGD record and publisher-version links; absent HTML remains metadata-only; annexes excluded.",
        provenance_behavior="Dataset 100354, stable law/version IDs, raw record hash and source-provided validity dates. Detection is not publication.",
        reuse_attribution="Zentraler Rechtsdienst / Open Data Basel-Stadt, CC BY 4.0; retain dataset and publisher links.",
        known_gaps=("German OGD representation; authoritative publication is the Kantonsblatt.",
                    "No court, parliament, complete gazette, OCR or annex-content coverage.",
                    "Upstream dataset is declared daily; late and corrected records appear on reconciliation. No deletion/repeal inference from absence.",
                    "A completed page/cycle establishes only traversal of the available dataset, not all cantonal developments."),
        localized_copy={locale: {"summary": NAME[locale], "boundary": SCOPE[locale]} for locale in NAME},
        last_verified_live_check="2026-09-09T05:52:00Z", evidence=evidence_class(bounded_live_smoke=True),
    ) for stream, cadence, window in (
        ("starter-de", "daily and explicitly requested first-use collection", "Current dataset entries for SG 153.260 (data protection) and SG 730.100 (building and planning) only"),
        ("latest-de", "hourly", "50 newest numeric version IDs, not 50 newest legal changes"),
        ("catalogue-de", "every 15 minutes", "20 records per page through all available dataset versions; resets after each complete cycle"),
    ))
