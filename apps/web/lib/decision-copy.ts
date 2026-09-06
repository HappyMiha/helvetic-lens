import type { Locale } from "./i18n";

type Copy = {
  title: string;
  modelExplanation: string;
  savedWording: string;
  interpretation: string;
  legacy: string;
  conditions: string;
  coverage: string;
  official: string;
  source: string;
  actionTitle: string;
  noAction: string;
  notReviewed: string;
  reviewActions: string;
  missing: string;
  statuses: Record<
    "proposal" | "enacted" | "repealed" | "mixed" | "unknown",
    string
  >;
};

// Product copy, pending independent native-language review.
export const decisionCopy: Record<Locale, Copy> = {
  "en-CH": {
    modelExplanation: "AI interpretation — verify against the sources",
    savedWording: "Saved wording only — not an AI explanation",
    title: "How to read this review",
    interpretation:
      "These are AI interpretations with source references, not verified legal conclusions. Check the conditions before acting.",
    legacy:
      "This saved report predates the structured decision review. Its applicability, status and empty action list were not verified under the current contract. Reassess explicitly to get a new report; this history stays unchanged.",
    conditions: "When this may affect your organization",
    coverage:
      "AI explanations: {explained} of {total} material changes. Other entries show saved wording only.",
    official: "Interpretation of legal status",
    source: "Inspect supporting sources",
    actionTitle: "Decision about next steps",
    noAction: "No action identified for now — review the stated conditions",
    notReviewed: "Next steps have not been established",
    reviewActions: "Actions suggested for human review",
    missing:
      "An empty action list does not establish that no action is needed.",
    statuses: {
      proposal: "Proposal",
      enacted: "Enacted",
      repealed: "Repealed",
      mixed: "Mixed statuses",
      unknown: "Not established",
    },
  },
  "de-CH": {
    modelExplanation: "KI-Interpretation — anhand der Quellen prüfen",
    savedWording: "Nur gespeicherter Wortlaut — keine KI-Erklärung",
    title: "So lesen Sie diese Einschätzung",
    interpretation:
      "Dies sind KI-Interpretationen mit Quellenangaben, keine geprüften rechtlichen Schlussfolgerungen. Prüfen Sie die Bedingungen, bevor Sie handeln.",
    legacy:
      "Dieser gespeicherte Bericht stammt aus der Zeit vor der strukturierten Entscheidungsprüfung. Anwendbarkeit, Status und eine leere Aktionsliste wurden nicht nach dem aktuellen Verfahren geprüft. Eine erneute Analyse erstellt einen neuen Bericht; dieser Verlauf bleibt unverändert.",
    conditions: "Wann dies Ihre Organisation betreffen kann",
    coverage:
      "KI-Erklärungen: {explained} von {total} wesentlichen Änderungen. Andere Einträge zeigen nur den gespeicherten Wortlaut.",
    official: "Interpretation des Rechtsstatus",
    source: "Belegende Quellen prüfen",
    actionTitle: "Entscheidung über nächste Schritte",
    noAction: "Derzeit keine Handlung erkannt — genannte Bedingungen prüfen",
    notReviewed: "Nächste Schritte sind noch nicht bestimmt",
    reviewActions: "Vorgeschlagene Handlungen zur menschlichen Prüfung",
    missing:
      "Eine leere Aktionsliste bedeutet nicht, dass keine Handlung erforderlich ist.",
    statuses: {
      proposal: "Entwurf",
      enacted: "Erlassen",
      repealed: "Aufgehoben",
      mixed: "Unterschiedliche Status",
      unknown: "Nicht festgestellt",
    },
  },
  "fr-CH": {
    modelExplanation: "Interprétation de l’IA — à vérifier dans les sources",
    savedWording: "Texte enregistré uniquement — sans explication de l’IA",
    title: "Comment lire cette analyse",
    interpretation:
      "Ce sont des interprétations de l’IA avec leurs sources, pas des conclusions juridiques vérifiées. Vérifiez les conditions avant d’agir.",
    legacy:
      "Ce rapport enregistré précède l’analyse structurée des décisions. Son applicabilité, son statut et une liste d’actions vide n’ont pas été vérifiés selon le contrat actuel. Relancez explicitement l’analyse pour créer un nouveau rapport ; cet historique reste inchangé.",
    conditions: "Quand votre organisation peut être concernée",
    coverage:
      "Explications de l’IA : {explained} sur {total} modifications substantielles. Les autres entrées montrent uniquement le texte enregistré.",
    official: "Interprétation du statut juridique",
    source: "Examiner les sources justificatives",
    actionTitle: "Décision sur les prochaines étapes",
    noAction:
      "Aucune action identifiée pour l’instant — vérifier les conditions",
    notReviewed: "Les prochaines étapes ne sont pas établies",
    reviewActions: "Actions proposées pour examen humain",
    missing: "Une liste vide ne prouve pas qu’aucune action n’est nécessaire.",
    statuses: {
      proposal: "Proposition",
      enacted: "Adopté",
      repealed: "Abrogé",
      mixed: "Statuts différents",
      unknown: "Non établi",
    },
  },
  "it-CH": {
    modelExplanation: "Interpretazione dell’IA — verificare nelle fonti",
    savedWording: "Solo testo salvato — senza spiegazione dell’IA",
    title: "Come leggere questa analisi",
    interpretation:
      "Queste sono interpretazioni dell’IA con riferimenti alle fonti, non conclusioni giuridiche verificate. Verificare le condizioni prima di agire.",
    legacy:
      "Questo rapporto salvato precede la verifica strutturata delle decisioni. Applicabilità, stato ed elenco vuoto di azioni non sono stati verificati secondo il contratto attuale. Una nuova analisi esplicita crea un nuovo rapporto; questa cronologia rimane invariata.",
    conditions: "Quando può riguardare la vostra organizzazione",
    coverage:
      "Spiegazioni dell’IA: {explained} di {total} modifiche sostanziali. Le altre voci mostrano solo il testo salvato.",
    official: "Interpretazione dello stato giuridico",
    source: "Esaminare le fonti a sostegno",
    actionTitle: "Decisione sui prossimi passi",
    noAction: "Nessuna azione individuata per ora — verificare le condizioni",
    notReviewed: "I prossimi passi non sono ancora stabiliti",
    reviewActions: "Azioni proposte per la revisione umana",
    missing:
      "Un elenco vuoto non dimostra che non sia necessaria alcuna azione.",
    statuses: {
      proposal: "Proposta",
      enacted: "Adottato",
      repealed: "Abrogato",
      mixed: "Stati diversi",
      unknown: "Non stabilito",
    },
  },
  "rm-CH": {
    modelExplanation: "Interpretaziun da l’IA — verifitgar cun las funtaunas",
    savedWording: "Mo text memorisà — nagina explicaziun da l’IA",
    title: "Co leger questa analisa",
    interpretation:
      "Questas èn interpretaziuns da l’IA cun funtaunas, betg conclusiuns giuridicas verifitgadas. Verifitgai las cundiziuns avant d’agir.",
    legacy:
      "Quest rapport memorisà deriva dal temp avant la controlla structurada da decisiuns. L’applicabladad, il status ed ina glista vida d’acziuns n’èn betg vegnids verifitgads tenor il contract actual. Ina nova analisa explicita creescha in nov rapport; questa cronologia resta senza midadas.",
    conditions: "Cura che quai po pertutgar Vossa organisaziun",
    coverage:
      "Explicaziuns da l’IA: {explained} da {total} midadas essenzialas. Las autras entradas mussan mo il text memorisà.",
    official: "Interpretaziun dal status giuridic",
    source: "Examinar las funtaunas",
    actionTitle: "Decisiun davart ils proxims pass",
    noAction:
      "Actualmain nagina acziun identifitgada — verifitgar las cundiziuns",
    notReviewed: "Ils proxims pass n’èn anc betg determinads",
    reviewActions: "Acziuns proponidas per la controlla umana",
    missing:
      "Ina glista vida na cumprova betg che nagina acziun saja necessaria.",
    statuses: {
      proposal: "Proposta",
      enacted: "Approvà",
      repealed: "Abolì",
      mixed: "Status differents",
      unknown: "Betg determinà",
    },
  },
};
