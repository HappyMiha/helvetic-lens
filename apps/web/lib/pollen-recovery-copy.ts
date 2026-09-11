import type { Locale } from "./i18n";
type Copy = { link: string; saved: string; unsaved: string };
export const pollenRecoveryCopy: Record<Locale, Copy> = {
  "en-CH": {
    link: "Link to this saved draft",
    saved:
      "This link reads the current saved settings after checking your access. Unsaved edits are not included.",
    unsaved:
      "Unsaved fields and retry keys stay only in this open form. After reloading, inspect saved drafts before creating another one if a previous save was uncertain.",
  },
  "de-CH": {
    link: "Link zu diesem gespeicherten Entwurf",
    saved:
      "Dieser Link lädt nach der Zugriffsprüfung die aktuell gespeicherten Einstellungen. Ungespeicherte Änderungen sind nicht enthalten.",
    unsaved:
      "Ungespeicherte Felder und Wiederholungsschlüssel bleiben nur in diesem offenen Formular. Prüfen Sie nach dem Neuladen die gespeicherten Entwürfe, bevor Sie einen weiteren erstellen, falls ein Speichervorgang unbestätigt war.",
  },
  "fr-CH": {
    link: "Lien vers ce brouillon enregistré",
    saved:
      "Ce lien lit les paramètres actuellement enregistrés après vérification de votre accès. Les modifications non enregistrées ne sont pas incluses.",
    unsaved:
      "Les champs non enregistrés et les clés de nouvelle tentative restent uniquement dans ce formulaire ouvert. Après un rechargement, vérifiez les brouillons enregistrés avant d’en créer un autre si un enregistrement était incertain.",
  },
  "it-CH": {
    link: "Link a questa bozza salvata",
    saved:
      "Questo link legge le impostazioni attualmente salvate dopo aver verificato l’accesso. Le modifiche non salvate non sono incluse.",
    unsaved:
      "I campi non salvati e le chiavi per riprovare restano solo in questo modulo aperto. Dopo aver ricaricato, controllate le bozze salvate prima di crearne un’altra se un salvataggio era incerto.",
  },
  "rm-CH": {
    link: "Link a quest sboz memorisà",
    saved:
      "Quest link legia ils parameters actualmain memorisads suenter la controlla da tes access. Midadas betg memorisadas n’èn betg inclusas.",
    unsaved:
      "Champs betg memorisads e clavs per empruvar danovamain restan mo en quest formular avert. Suenter rechargiar, controllescha ils sbozs memorisads avant da crear in auter, sch’ina memorisaziun era intscherta.",
  },
};
