import type { Locale } from "./i18n";
export type BriefReuse = {
  items: Array<{
    surface: "reader" | "notifications" | "digest_preview";
    projections: number;
    first_at: string;
    last_at: string;
  }>;
  start_day: string;
  end_day: string;
  calendar_timezone: "UTC";
};
export const briefReuseCopy: Record<
  Locale,
  {
    title: string;
    help: string;
    empty: string;
    reader: string;
    notifications: string;
    digest_preview: string;
    count: string;
  }
> = {
  "en-CH": {
    title: "Saved brief reuse",
    help: "Daily UTC totals of validated saved briefs returned by the server. These are not confirmed views, unique users, email deliveries or estimated token savings. Refreshes may count again; browser-only cache reads do not. Collection can miss observations; there is no historical backfill or personal activity log.",
    empty:
      "No recorded reuse in this period; this does not prove there was none.",
    reader: "Brief reader (Today / Marvin)",
    notifications: "Notification responses",
    digest_preview: "Digest previews",
    count: "Recorded server projections",
  },
  "de-CH": {
    title: "Wiederverwendung gespeicherter Analysen",
    help: "UTC-Tagessummen validierter gespeicherter Analysen, die der Server zurückgegeben hat. Keine bestätigten Ansichten, einzelnen Nutzer, E-Mail-Zustellungen oder geschätzten Tokeneinsparungen. Aktualisierungen können erneut zählen, reine Browsercache-Abrufe nicht. Beobachtungen können fehlen; keine historische Ergänzung oder persönliche Aktivitätschronik.",
    empty:
      "Keine Wiederverwendung in diesem Zeitraum erfasst; dies beweist nicht, dass es keine gab.",
    reader: "Analyseleser (Heute / Marvin)",
    notifications: "Benachrichtigungsantworten",
    digest_preview: "Digest-Vorschauen",
    count: "Erfasste Serverausgaben",
  },
  "fr-CH": {
    title: "Réutilisation des analyses enregistrées",
    help: "Totaux quotidiens UTC des analyses enregistrées validées renvoyées par le serveur. Ce ne sont pas des vues confirmées, utilisateurs uniques, livraisons de courriels ou économies estimées de jetons. Les actualisations peuvent compter à nouveau, pas les lectures du cache du navigateur. Des observations peuvent manquer ; sans reconstitution historique ni suivi individuel.",
    empty:
      "Aucune réutilisation enregistrée pour cette période ; cela ne prouve pas son absence.",
    reader: "Lecteur d’analyses (Aujourd’hui / Marvin)",
    notifications: "Réponses de notifications",
    digest_preview: "Aperçus de synthèses",
    count: "Projections serveur enregistrées",
  },
  "it-CH": {
    title: "Riutilizzo delle analisi salvate",
    help: "Totali giornalieri UTC delle analisi salvate validate restituite dal server. Non sono visualizzazioni confermate, utenti unici, email consegnate o risparmi stimati di token. Gli aggiornamenti possono contare di nuovo, le letture dalla sola cache del browser no. Possono mancare osservazioni; nessuna ricostruzione storica o cronologia personale.",
    empty:
      "Nessun riutilizzo registrato nel periodo; non significa che non ce ne sia stato.",
    reader: "Lettore analisi (Oggi / Marvin)",
    notifications: "Risposte di notifiche",
    digest_preview: "Anteprime dei riepiloghi",
    count: "Proiezioni server registrate",
  },
  "rm-CH": {
    title: "Reutilisaziun d’analisas memorisadas",
    help: "Totals da mintga di UTC d’analisas memorisadas validatas che il server ha returnà. Quai n’èn betg vistas confermadas, utilisaders unics, e-mails consegnads u tokens spargnads stimads. Actualisaziuns pon quintar danovamain, lecturas mo dal cache dal navigatur betg. Observaziuns pon mancar; nagina reconstrucziun istorica u cronologia persunala.",
    empty:
      "Nagina reutilisaziun registrada en questa perioda; quai na cumprova betg ch’i na deva nagina.",
    reader: "Lectur d’analisas (Oz / Marvin)",
    notifications: "Respostas da notificaziuns",
    digest_preview: "Previsualisaziuns da resums",
    count: "Projecziuns dal server registradas",
  },
};
