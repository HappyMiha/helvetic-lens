"""Honest server-authored copy for the small-model evidence-selection adapter."""

COPY = {
    "en-CH": {
        "headline": "Selected evidence — impact not assessed",
        "summary": "The model selected saved passages for review. It did not produce an explanation of their legal or organizational impact.",
        "empty_summary": "No saved passage was selected. The possible relation and its impact require human review; no action recommendation has been generated.",
        "reason": "Open the citations and compare the saved wording. Applicability, importance, dates and required actions have not been assessed; this does not mean that no action is needed.",
        "earlier": "Earlier saved wording",
        "current": "Current saved wording",
    },
    "de-CH": {
        "headline": "Ausgewählte Belege — Auswirkungen nicht beurteilt",
        "summary": "Das Modell hat gespeicherte Passagen zur Prüfung ausgewählt. Es hat ihre rechtlichen oder organisatorischen Auswirkungen nicht erklärt.",
        "empty_summary": "Es wurde keine gespeicherte Passage ausgewählt. Die mögliche Beziehung und ihre Auswirkungen müssen manuell geprüft werden; es wurde keine Handlungsempfehlung erstellt.",
        "reason": "Öffnen Sie die Belege und vergleichen Sie den gespeicherten Wortlaut. Anwendbarkeit, Bedeutung, Termine und erforderliche Massnahmen wurden nicht beurteilt; das bedeutet nicht, dass kein Handlungsbedarf besteht.",
        "earlier": "Früherer gespeicherter Wortlaut",
        "current": "Aktueller gespeicherter Wortlaut",
    },
    "fr-CH": {
        "headline": "Éléments sélectionnés — impact non évalué",
        "summary": "Le modèle a sélectionné des passages enregistrés à examiner. Il n’a pas expliqué leur impact juridique ou organisationnel.",
        "empty_summary": "Aucun passage enregistré n’a été sélectionné. La relation possible et son impact nécessitent un examen humain ; aucune recommandation d’action n’a été produite.",
        "reason": "Ouvrez les citations et comparez les textes enregistrés. L’applicabilité, l’importance, les dates et les actions requises n’ont pas été évaluées; cela ne signifie pas qu’aucune action n’est nécessaire.",
        "earlier": "Texte antérieur enregistré",
        "current": "Texte actuel enregistré",
    },
    "it-CH": {
        "headline": "Prove selezionate — impatto non valutato",
        "summary": "Il modello ha selezionato passaggi salvati da esaminare. Non ha spiegato il loro impatto giuridico o organizzativo.",
        "empty_summary": "Non è stato selezionato alcun passaggio salvato. La possibile relazione e il suo impatto richiedono una verifica umana; non è stata formulata alcuna raccomandazione operativa.",
        "reason": "Apri le citazioni e confronta i testi salvati. Applicabilità, importanza, date e azioni necessarie non sono state valutate; ciò non significa che non occorra agire.",
        "earlier": "Testo precedente salvato",
        "current": "Testo attuale salvato",
    },
    "rm-CH": {
        "headline": "Cumprovas tschernidas — influenza betg valitada",
        "summary": "Il model ha tschernì passadis memorisads per l’examinaziun. El n’ha betg explitgà lur influenza giuridica u organisatorica.",
        "empty_summary": "Nagin passadi memorisà n’è vegnì tschernì. La relaziun pussaivla e sia influenza dovran ina controlla umana; nagina recumandaziun d’agir n’è vegnida generada.",
        "reason": "Avri las citaziuns e cumparegliai ils texts memorisads. L’applicabladad, l’impurtanza, las datas e las mesiras necessarias n’èn betg vegnidas valitadas; quai na signifitga betg ch’i na dovria naginas mesiras.",
        "earlier": "Text precedent memorisà",
        "current": "Text actual memorisà",
    },
}


def selected_evidence_copy(locale: str) -> dict[str, str]:
    return COPY.get(locale, COPY["en-CH"])
