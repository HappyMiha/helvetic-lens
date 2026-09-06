import type { Locale } from "./i18n";

type Copy = {
  page: string;
  shown: string;
  total: string;
  before: string;
  previous: string;
  next: string;
  restart: string;
  retry: string;
  loading: string;
  empty: string;
  help: string;
  choices: string;
  browse: string;
};
export const documentHistoryCopy: Record<Locale, Copy> = {
  "en-CH": {
    page: "Page",
    shown: "On this page",
    total: "Currently accessible saved records",
    before: "Saved by",
    previous: "Previous page",
    next: "Next page",
    restart: "Show latest records",
    retry: "Retry this page",
    loading: "Loading saved history…",
    empty: "No saved records on this page.",
    help: "Browse every saved record. New saves appear after refreshing; corrections or removals can change an older page. This is saved history, not proof of complete source coverage.",
    choices:
      "Choices include recent versions, this history page and your selections. Browse older pages to choose another version; your current selections stay in the form.",
    browse: "Browse saved versions",
  },
  "de-CH": {
    page: "Seite",
    shown: "Auf dieser Seite",
    total: "Derzeit zugängliche gespeicherte Einträge",
    before: "Gespeichert bis",
    previous: "Vorherige Seite",
    next: "Nächste Seite",
    restart: "Neueste Einträge anzeigen",
    retry: "Seite erneut laden",
    loading: "Gespeicherten Verlauf laden…",
    empty: "Keine gespeicherten Einträge auf dieser Seite.",
    help: "Blättern Sie durch alle gespeicherten Einträge. Neue Einträge erscheinen nach dem Aktualisieren; Korrekturen oder Löschungen können ältere Seiten verändern. Der Verlauf belegt keine vollständige Quellenabdeckung.",
    choices:
      "Die Auswahl enthält aktuelle Versionen, diese Verlaufsseite und Ihre Auswahl. Blättern Sie zu älteren Seiten, um eine weitere Version zu wählen; Ihre Auswahl bleibt im Formular erhalten.",
    browse: "Gespeicherte Versionen durchsuchen",
  },
  "fr-CH": {
    page: "Page",
    shown: "Sur cette page",
    total: "Enregistrements sauvegardés actuellement accessibles",
    before: "Sauvegardés au plus tard le",
    previous: "Page précédente",
    next: "Page suivante",
    restart: "Afficher les derniers enregistrements",
    retry: "Réessayer cette page",
    loading: "Chargement de l’historique sauvegardé…",
    empty: "Aucun enregistrement sauvegardé sur cette page.",
    help: "Parcourez tous les enregistrements sauvegardés. Les nouveaux apparaissent après actualisation ; des corrections ou suppressions peuvent modifier une ancienne page. Cet historique ne prouve pas une couverture complète des sources.",
    choices:
      "La liste comprend les versions récentes, cette page d’historique et vos sélections. Parcourez les anciennes pages pour choisir une autre version ; vos sélections restent dans le formulaire.",
    browse: "Parcourir les versions sauvegardées",
  },
  "it-CH": {
    page: "Pagina",
    shown: "In questa pagina",
    total: "Record salvati attualmente accessibili",
    before: "Salvati entro",
    previous: "Pagina precedente",
    next: "Pagina successiva",
    restart: "Mostra i record più recenti",
    retry: "Riprova questa pagina",
    loading: "Caricamento della cronologia salvata…",
    empty: "Nessun record salvato in questa pagina.",
    help: "Sfoglia tutti i record salvati. I nuovi compaiono dopo l’aggiornamento; correzioni o eliminazioni possono modificare una pagina precedente. Questa cronologia non dimostra una copertura completa delle fonti.",
    choices:
      "Le opzioni includono le versioni recenti, questa pagina e le tue selezioni. Sfoglia le pagine precedenti per scegliere un’altra versione; le tue selezioni rimangono nel modulo.",
    browse: "Sfoglia le versioni salvate",
  },
  "rm-CH": {
    page: "Pagina",
    shown: "Sin questa pagina",
    total: "Endataziuns memorisadas actualmain accessiblas",
    before: "Memorisà fin",
    previous: "Pagina precedenta",
    next: "Proxima pagina",
    restart: "Mussar las endataziuns las pli novas",
    retry: "Empruvar anc ina giada questa pagina",
    loading: "Chargiar l’istorgia memorisada…",
    empty: "Naginas endataziuns memorisadas sin questa pagina.",
    help: "Sfegliai tut las endataziuns memorisadas. Novas endataziuns cumparan suenter l’actualisaziun; correcturas u stizzadas pon midar paginas pli veglias. Questa istorgia na cumprova betg ina cuvrida cumpletta da las funtaunas.",
    choices:
      "La selecziun cuntegna versiuns recentas, questa pagina e Vossas selecziuns. Sfegliai paginas pli veglias per tscherner in’autra versiun; Vossas selecziuns restan en il formular.",
    browse: "Sfegliar las versiuns memorisadas",
  },
};
