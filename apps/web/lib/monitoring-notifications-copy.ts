import type { Locale } from "./i18n";

type Copy = {
  body: string;
  overview: string;
  empty: string;
  sparse: string;
  unavailable: string;
  failed: string;
  open: string;
  saved: string;
};
export const monitoringNotificationsCopy: Record<Locale, Copy> = {
  "en-CH": {
    body: "Review saved changes in your nine Monitoring directions and legal feed. Choose a queue, then open its evidence. Opening a notification does not mark it reviewed.",
    overview: "All review queues",
    empty:
      "No readable changes await review in this queue. Check the section for source availability.",
    sparse:
      "No readable entries on this page. More saved entries can be checked on the next page.",
    unavailable:
      "This queue is currently unavailable. You can still open its section to inspect source access and settings.",
    failed:
      "The queue could not be loaded. Previous results have been cleared; reload to check current access.",
    open: "Open saved change",
    saved: "Saved change awaiting review",
  },
  "de-CH": {
    body: "Prüfen Sie gespeicherte Änderungen aus Ihren neun Monitoring-Bereichen und dem Rechtsfeed. Wählen Sie eine Liste und öffnen Sie die Nachweise. Das Öffnen einer Meldung markiert sie nicht als geprüft.",
    overview: "Alle Prüflisten",
    empty:
      "Keine lesbaren Änderungen warten in dieser Liste auf Prüfung. Die Quellenverfügbarkeit steht im jeweiligen Bereich.",
    sparse:
      "Auf dieser Seite gibt es keine lesbaren Einträge. Weitere gespeicherte Einträge können auf der nächsten Seite geprüft werden.",
    unavailable:
      "Diese Liste ist derzeit nicht verfügbar. Im zugehörigen Bereich können Sie Quellenzugriff und Einstellungen prüfen.",
    failed:
      "Die Liste konnte nicht geladen werden. Frühere Ergebnisse wurden entfernt; laden Sie sie für eine aktuelle Zugriffsprüfung neu.",
    open: "Gespeicherte Änderung öffnen",
    saved: "Gespeicherte Änderung zur Prüfung",
  },
  "fr-CH": {
    body: "Examinez les changements enregistrés dans vos neuf rubriques de veille et le fil juridique. Choisissez une liste, puis ouvrez ses preuves. Ouvrir une notification ne la marque pas comme examinée.",
    overview: "Toutes les listes à examiner",
    empty:
      "Aucun changement lisible n’attend d’examen dans cette liste. Vérifiez la disponibilité des sources dans la rubrique.",
    sparse:
      "Aucune entrée lisible sur cette page. La page suivante permet de vérifier d’autres entrées enregistrées.",
    unavailable:
      "Cette liste est actuellement indisponible. Vous pouvez ouvrir sa rubrique pour vérifier l’accès aux sources et les paramètres.",
    failed:
      "La liste n’a pas pu être chargée. Les anciens résultats ont été effacés ; rechargez pour vérifier l’accès actuel.",
    open: "Ouvrir le changement enregistré",
    saved: "Changement enregistré à examiner",
  },
  "it-CH": {
    body: "Esamina le modifiche salvate nelle nove sezioni di monitoraggio e nel flusso giuridico. Scegli una lista e apri le evidenze. Aprire una notifica non la segna come esaminata.",
    overview: "Tutte le liste da esaminare",
    empty:
      "Nessuna modifica leggibile attende un esame in questa lista. Controlla la disponibilità delle fonti nella sezione.",
    sparse:
      "Nessuna voce leggibile in questa pagina. Puoi controllare altre voci salvate nella pagina successiva.",
    unavailable:
      "Questa lista non è attualmente disponibile. Puoi aprire la sezione per verificare l’accesso alle fonti e le impostazioni.",
    failed:
      "Impossibile caricare la lista. I risultati precedenti sono stati rimossi; ricarica per verificare l’accesso attuale.",
    open: "Apri modifica salvata",
    saved: "Modifica salvata da esaminare",
  },
  "rm-CH": {
    body: "Controllai las midadas memorisadas en Voss nov secturs da monitoring ed en il fluss giuridic. Tscherni ina glista ed avri las cumprovas. Avrir ina notificaziun na la marca betg sco controllada.",
    overview: "Tut las glistas da controllar",
    empty:
      "Naginas midadas legiblas spetgan sin ina controlla en questa glista. Controllai la disponibladad da las funtaunas en il sectur.",
    sparse:
      "Naginas endataziuns legiblas sin questa pagina. Sin la proxima pagina pon vegnir controlladas ulteriuras endataziuns memorisadas.",
    unavailable:
      "Questa glista n’è actualmain betg disponibla. Vus pudais avrir ses sectur per controllar l’access a las funtaunas ed ils parameters.",
    failed:
      "La glista n’ha betg pudì vegnir chargiada. Ils resultats anteriurs èn vegnids allontanads; chargiai danovamain per controllar l’access actual.",
    open: "Avrir la midada memorisada",
    saved: "Midada memorisada da controllar",
  },
};
