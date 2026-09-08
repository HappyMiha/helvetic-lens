import type { Locale } from "./i18n";

type Copy = {
  title: string;
  body: string;
  empty: string;
  sparse: string;
  count: string;
  cadence: string;
  stale: string;
  read: string;
  dismiss: string;
};
export const notificationCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Notifications",
    body: "Unread developments for your organization’s monitored interests. One entry per event; open it for relevance, saved analysis and original evidence.",
    empty:
      "No unread developments in this selection. This does not mean every source is up to date.",
    sparse:
      "No eligible unread developments in this batch. Continue to check older records.",
    count: "Unread on this page",
    cadence:
      "Refreshes every minute while open and visible. Dates show when we detected an event, not when a law took effect. Reading state is personal and saved across sessions.",
    stale: "Could not refresh. Previously loaded records may be out of date.",
    read: "Mark as read",
    dismiss: "Dismiss",
  },
  "de-CH": {
    title: "Benachrichtigungen",
    body: "Ungelesene Entwicklungen zu den Interessen Ihrer Organisation. Ein Eintrag pro Ereignis; öffnen Sie ihn für Relevanz, gespeicherte Analyse und Originalbelege.",
    empty:
      "Keine ungelesenen Entwicklungen in dieser Auswahl. Das bedeutet nicht, dass alle Quellen aktuell sind.",
    sparse:
      "Keine passenden ungelesenen Entwicklungen in diesem Datenblock. Prüfen Sie die älteren Einträge.",
    count: "Ungelesen auf dieser Seite",
    cadence:
      "Aktualisierung jede Minute, solange geöffnet und sichtbar. Das Datum zeigt die Erkennung, nicht das Inkrafttreten. Ihr Lesestatus wird sitzungsübergreifend gespeichert.",
    stale:
      "Aktualisierung fehlgeschlagen. Bereits geladene Einträge können veraltet sein.",
    read: "Als gelesen markieren",
    dismiss: "Ausblenden",
  },
  "fr-CH": {
    title: "Notifications",
    body: "Évolutions non lues liées aux intérêts suivis par votre organisation. Une entrée par événement ; ouvrez-la pour consulter sa pertinence, l’analyse enregistrée et les sources.",
    empty:
      "Aucune évolution non lue dans cette sélection. Cela ne signifie pas que toutes les sources sont à jour.",
    sparse:
      "Aucune évolution non lue admissible dans ce lot. Consultez les enregistrements plus anciens.",
    count: "Non lues sur cette page",
    cadence:
      "Actualisation chaque minute tant que ce panneau reste ouvert et visible. La date indique la détection, pas l’entrée en vigueur. Votre état de lecture personnel est conservé entre les sessions.",
    stale:
      "Actualisation impossible. Les éléments déjà chargés peuvent être périmés.",
    read: "Marquer comme lu",
    dismiss: "Masquer",
  },
  "it-CH": {
    title: "Notifiche",
    body: "Sviluppi non letti relativi agli interessi monitorati dalla tua organizzazione. Una voce per evento; aprila per consultare pertinenza, analisi salvata e fonti originali.",
    empty:
      "Nessuno sviluppo non letto in questa selezione. Non significa che tutte le fonti siano aggiornate.",
    sparse:
      "Nessuno sviluppo non letto idoneo in questo gruppo. Continua con i dati precedenti.",
    count: "Non letti su questa pagina",
    cadence:
      "Aggiornamento ogni minuto mentre il pannello è aperto e visibile. La data indica il rilevamento, non l’entrata in vigore. Lo stato di lettura personale viene conservato tra le sessioni.",
    stale:
      "Aggiornamento non riuscito. I dati già caricati potrebbero essere superati.",
    read: "Segna come letto",
    dismiss: "Nascondi",
  },
  "rm-CH": {
    title: "Communicaziuns",
    body: "Svilups betg legids davart ils interess survegliads da Vossa organisaziun. Ina endataziun per eveniment; avri ella per la relevanza, l’analisa memorisada e las funtaunas originalas.",
    empty:
      "Nagins svilups betg legids en questa selecziun. Quai na munta betg che tut las funtaunas èn actualas.",
    sparse:
      "Nagins svilups betg legids adattads en quest bloc. Cuntinuai cun las endataziuns pli veglias.",
    count: "Betg legids sin questa pagina",
    cadence:
      "Actualisaziun mintga minuta, uschè ditg che la fanestra è averta e visibla. La data inditgescha la detecziun, betg l’entrada en vigur. Voss stadi da lectura persunal resta memorisà tranter las sessiuns.",
    stale:
      "L’actualisaziun n’è betg reussida. Las endataziuns chargiadas pon esser antiquadas.",
    read: "Marcar sco legì",
    dismiss: "Zuppentar",
  },
};
