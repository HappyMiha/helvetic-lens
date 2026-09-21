import type { Locale } from "./i18n";

export const documentScheduleCopy: Record<
  Locale,
  { label: string; help: string; next: string; manual: string }
> = {
  "en-CH": {
    label: "Check this document daily",
    help: "Retrieve the saved source and compare it with the previous version. Pausing the document also pauses daily checks. No email is sent by this setting.",
    next: "Next check after",
    manual: "Manual checks only",
  },
  "de-CH": {
    label: "Dieses Dokument täglich prüfen",
    help: "Gespeicherte Quelle abrufen und mit der vorherigen Fassung vergleichen. Eine Pause des Dokuments pausiert auch die täglichen Prüfungen. Diese Einstellung versendet keine E-Mail.",
    next: "Nächste Prüfung ab",
    manual: "Nur manuelle Prüfungen",
  },
  "fr-CH": {
    label: "Vérifier ce document chaque jour",
    help: "Récupérer la source enregistrée et la comparer à la version précédente. Mettre le document en pause suspend aussi les vérifications quotidiennes. Ce réglage n’envoie aucun courriel.",
    next: "Prochaine vérification après",
    manual: "Vérifications manuelles uniquement",
  },
  "it-CH": {
    label: "Controlla questo documento ogni giorno",
    help: "Recupera la fonte salvata e confrontala con la versione precedente. La pausa del documento sospende anche i controlli giornalieri. Questa impostazione non invia email.",
    next: "Prossimo controllo dopo",
    manual: "Solo controlli manuali",
  },
  "rm-CH": {
    label: "Controllar quest document mintga di",
    help: "Clamar la funtauna memorisada e cumparegliar cun la versiun precedenta. Ina pausa dal document metta er en pausa las controllas quotidianas. Questa configuraziun na trametta naginas e-mails.",
    next: "Proxima controlla suenter",
    manual: "Mo controllas manualas",
  },
};
