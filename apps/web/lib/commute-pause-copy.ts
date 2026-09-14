import type { Locale } from "./i18n";

export const commutePauseTimezone = "Europe/Zurich";

export const commutePauseCopy: Record<
  Locale,
  { title: string; until: string; help: string; ended: string }
> = {
  "en-CH": {
    title: "Commute notifications paused today",
    until: "Today's pause ends",
    help: "Source checks may continue. After midnight, your saved days and travel windows apply again; this does not guarantee source availability. Open settings to continue today or pause indefinitely.",
    ended:
      "Today's notification pause has ended. Your saved days and travel windows apply again, subject to source availability.",
  },
  "de-CH": {
    title: "Pendlerbenachrichtigungen heute pausiert",
    until: "Die heutige Pause endet",
    help: "Quellenprüfungen können weiterlaufen. Nach Mitternacht gelten wieder Ihre gespeicherten Tage und Reisezeiten; die Quellenverfügbarkeit ist nicht garantiert. In den Einstellungen können Sie heute fortsetzen oder unbefristet pausieren.",
    ended:
      "Die heutige Benachrichtigungspause ist beendet. Ihre gespeicherten Tage und Reisezeiten gelten wieder, sofern die Quellen verfügbar sind.",
  },
  "fr-CH": {
    title: "Notifications de trajet en pause aujourd'hui",
    until: "Fin de la pause du jour",
    help: "Les vérifications des sources peuvent continuer. Après minuit, vos jours et horaires enregistrés s'appliquent à nouveau, sans garantie de disponibilité des sources. Ouvrez les paramètres pour reprendre aujourd'hui ou suspendre sans limite de durée.",
    ended:
      "La pause des notifications du jour est terminée. Vos jours et horaires enregistrés s'appliquent à nouveau, sous réserve de disponibilité des sources.",
  },
  "it-CH": {
    title: "Notifiche del tragitto sospese oggi",
    until: "La pausa di oggi termina",
    help: "I controlli delle fonti possono continuare. Dopo mezzanotte si applicano di nuovo i giorni e gli orari salvati; la disponibilità delle fonti non è garantita. Apri le impostazioni per riprendere oggi o sospendere senza scadenza.",
    ended:
      "La pausa delle notifiche di oggi è terminata. Si applicano di nuovo i giorni e gli orari salvati, se le fonti sono disponibili.",
  },
  "rm-CH": {
    title: "Avis dal viadi en pausa oz",
    until: "La pausa dad oz finescha",
    help: "Las controllas da las funtaunas pon cuntinuar. Suenter mesanotg valan puspè ils dis e temps da viadi memorisads; la disponibladad da las funtaunas n'è betg garantida. Avri ils parameters per cuntinuar oz u far pausa senza termin.",
    ended:
      "La pausa dals avis dad oz è terminada. Ils dis e temps da viadi memorisads valan puspè, sche las funtaunas èn disponiblas.",
  },
};
