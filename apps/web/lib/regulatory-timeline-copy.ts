import type { Locale } from "./i18n";

export const regulatoryTimelineCopy: Record<
  Locale,
  {
    version: string;
    comparison: string;
    event: string;
    sources: string;
    help: string;
  }
> = {
  "en-CH": {
    version: "Saved version",
    comparison: "Saved comparison",
    event: "Detected development",
    sources: "Source observations",
    help: "Browse the complete saved record, one page at a time. Timeline dates show detection or saving, not when a law came into force. Opening a page does not scan a website or ask AI.",
  },
  "de-CH": {
    version: "Gespeicherte Fassung",
    comparison: "Gespeicherter Vergleich",
    event: "Erkannte Entwicklung",
    sources: "Quellenbeobachtungen",
    help: "Lesen Sie den vollständigen gespeicherten Verlauf Seite für Seite. Die Zeitangaben zeigen Erkennung oder Speicherung, nicht das Inkrafttreten. Beim Blättern werden weder Websites abgefragt noch KI-Anfragen gesendet.",
  },
  "fr-CH": {
    version: "Version enregistrée",
    comparison: "Comparaison enregistrée",
    event: "Évolution détectée",
    sources: "Observations des sources",
    help: "Parcourez l’intégralité de l’historique enregistré, page par page. Les dates indiquent la détection ou l’enregistrement, pas l’entrée en vigueur. La consultation ne lance ni scan de site ni requête IA.",
  },
  "it-CH": {
    version: "Versione salvata",
    comparison: "Confronto salvato",
    event: "Sviluppo rilevato",
    sources: "Osservazioni delle fonti",
    help: "Consulta tutta la cronologia salvata, una pagina alla volta. Le date indicano il rilevamento o il salvataggio, non l’entrata in vigore. La consultazione non avvia scansioni di siti né richieste all’IA.",
  },
  "rm-CH": {
    version: "Versiun memorisada",
    comparison: "Cumparegliaziun memorisada",
    event: "Svilup constatà",
    sources: "Observaziuns da las funtaunas",
    help: "Legiai l’entira cronologia memorisada, pagina per pagina. Las datas inditgeschan la constataziun u memorisaziun, betg l’entrada en vigur. La lectura na lantscha ni scans da websites ni dumondas a l’IA.",
  },
};
