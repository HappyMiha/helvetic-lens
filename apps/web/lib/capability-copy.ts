import type { Locale } from "./i18n";

type Copy = {
  title: string;
  none: string;
  unavailable: string;
  help: string;
  invalid: string;
  empty: string;
  approved: string;
  candidate: string;
  revoked: string;
  ask: string;
  impact_report: string;
};

// Profile metadata is server-verified. These labels never approve a model.
export const capabilityCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Explanation profile",
    none: "Evidence selection only",
    unavailable: "Saved profile unavailable",
    help: "Explanations require a reviewed profile matching the running model, task and language. Selecting a profile does not download or switch models.",
    invalid:
      "The review registry could not be verified. Explanations are disabled.",
    empty:
      "No reviewed profiles are installed. Cited evidence remains available; it is not an impact assessment.",
    approved: "Reviewed",
    candidate: "Not reviewed",
    revoked: "Withdrawn",
    ask: "Questions",
    impact_report: "Impact reports",
  },
  "de-CH": {
    title: "Erklärungsprofil",
    none: "Nur Belege auswählen",
    unavailable: "Gespeichertes Profil nicht verfügbar",
    help: "Erklärungen erfordern ein geprüftes Profil für das laufende Modell, die Aufgabe und die Sprache. Die Profilauswahl lädt oder wechselt kein Modell.",
    invalid:
      "Das Prüfregister konnte nicht verifiziert werden. Erklärungen sind deaktiviert.",
    empty:
      "Es sind keine geprüften Profile installiert. Zitierte Belege bleiben verfügbar; sie sind keine Folgenabschätzung.",
    approved: "Geprüft",
    candidate: "Nicht geprüft",
    revoked: "Zurückgezogen",
    ask: "Fragen",
    impact_report: "Wirkungsberichte",
  },
  "fr-CH": {
    title: "Profil d’explication",
    none: "Sélection de preuves uniquement",
    unavailable: "Profil enregistré indisponible",
    help: "Les explications nécessitent un profil évalué correspondant au modèle actif, à la tâche et à la langue. Choisir un profil ne télécharge ni ne change le modèle.",
    invalid:
      "Le registre des évaluations n’a pas pu être vérifié. Les explications sont désactivées.",
    empty:
      "Aucun profil évalué n’est installé. Les preuves citées restent disponibles ; elles ne constituent pas une analyse d’impact.",
    approved: "Évalué",
    candidate: "Non évalué",
    revoked: "Retiré",
    ask: "Questions",
    impact_report: "Rapports d’impact",
  },
  "it-CH": {
    title: "Profilo di spiegazione",
    none: "Solo selezione delle prove",
    unavailable: "Profilo salvato non disponibile",
    help: "Le spiegazioni richiedono un profilo valutato per il modello attivo, il compito e la lingua. Selezionare un profilo non scarica né cambia il modello.",
    invalid:
      "Impossibile verificare il registro delle valutazioni. Le spiegazioni sono disattivate.",
    empty:
      "Nessun profilo valutato installato. Le prove citate restano disponibili; non costituiscono una valutazione d’impatto.",
    approved: "Valutato",
    candidate: "Non valutato",
    revoked: "Ritirato",
    ask: "Domande",
    impact_report: "Rapporti d’impatto",
  },
  "rm-CH": {
    title: "Profil d’explicaziun",
    none: "Mo selecziun da cumprovas",
    unavailable: "Profil memorisà betg disponibel",
    help: "Explicaziuns dovran in profil examinà per il model activ, l’incumbensa e la lingua. Tscherner in profil na chargia betg giu e na mida betg il model.",
    invalid:
      "Il register da las examinaziuns n’ha betg pudì vegnir verifitgà. Las explicaziuns èn deactivadas.",
    empty:
      "Nagins profils examinads èn installads. Las cumprovas citadas restan disponiblas; ellas n’èn betg ina valitaziun d’impact.",
    approved: "Examinà",
    candidate: "Betg examinà",
    revoked: "Retratg",
    ask: "Dumondas",
    impact_report: "Rapports d’impact",
  },
};
