import type { Locale } from "./i18n";

type Copy = {
  remove: string;
  confirm: string;
  busy: string;
  deleted: string;
  conflict: string;
  reload: string;
  uncertain: string;
};
export const pollenDeleteCopy: Record<Locale, Copy> = {
  "en-CH": {
    remove: "Delete draft",
    confirm:
      "Delete the private draft for station {station}, revision {revision}? All its saved configuration and evaluation history will also be removed. This cannot be undone.",
    busy: "Deleting draft…",
    deleted: "The draft and its private history were deleted.",
    conflict:
      "The draft changed or is no longer deletable. Reload it and review the current revision before trying again.",
    reload: "Reload selected draft",
    uncertain:
      "Deletion could not be confirmed. You may retry the same revision or reload to check whether the draft still exists.",
  },
  "de-CH": {
    remove: "Entwurf löschen",
    confirm:
      "Den privaten Entwurf für Station {station}, Version {revision}, löschen? Alle gespeicherten Einstellungen und der Auswertungsverlauf werden ebenfalls entfernt. Dies kann nicht rückgängig gemacht werden.",
    busy: "Entwurf wird gelöscht…",
    deleted: "Der Entwurf und sein privater Verlauf wurden gelöscht.",
    conflict:
      "Der Entwurf wurde geändert oder kann nicht mehr gelöscht werden. Laden Sie ihn neu und prüfen Sie die aktuelle Version vor einem erneuten Versuch.",
    reload: "Ausgewählten Entwurf neu laden",
    uncertain:
      "Die Löschung konnte nicht bestätigt werden. Wiederholen Sie den Versuch mit derselben Version oder laden Sie neu, um zu prüfen, ob der Entwurf noch existiert.",
  },
  "fr-CH": {
    remove: "Supprimer le brouillon",
    confirm:
      "Supprimer le brouillon privé de la station {station}, révision {revision} ? Tous ses paramètres enregistrés et son historique d’évaluation seront également supprimés. Cette action est irréversible.",
    busy: "Suppression du brouillon…",
    deleted: "Le brouillon et son historique privé ont été supprimés.",
    conflict:
      "Le brouillon a changé ou ne peut plus être supprimé. Rechargez-le et vérifiez la révision actuelle avant de réessayer.",
    reload: "Recharger le brouillon sélectionné",
    uncertain:
      "La suppression n’a pas pu être confirmée. Réessayez avec la même révision ou rechargez pour vérifier si le brouillon existe encore.",
  },
  "it-CH": {
    remove: "Elimina bozza",
    confirm:
      "Eliminare la bozza privata della stazione {station}, revisione {revision}? Verranno eliminate anche tutte le impostazioni salvate e la cronologia delle valutazioni. L’azione è irreversibile.",
    busy: "Eliminazione della bozza…",
    deleted: "La bozza e la sua cronologia privata sono state eliminate.",
    conflict:
      "La bozza è cambiata o non può più essere eliminata. Ricaricatela e verificate la revisione attuale prima di riprovare.",
    reload: "Ricarica bozza selezionata",
    uncertain:
      "L’eliminazione non è stata confermata. Riprovate con la stessa revisione o ricaricate per verificare se la bozza esiste ancora.",
  },
  "rm-CH": {
    remove: "Stizzar il sboz",
    confirm:
      "Stizzar il sboz privat per la staziun {station}, versiun {revision}? Tut ses parameters memorisads e sia istorgia d’evaluaziun vegnan era stizzads. Quai na po betg vegnir revocà.",
    busy: "Stizzar il sboz…",
    deleted: "Il sboz e sia istorgia privata èn vegnids stizzads.",
    conflict:
      "Il sboz è sa midà u na po betg pli vegnir stizzà. Rechargia el e controllescha la versiun actuala avant d’empruvar danovamain.",
    reload: "Rechargiar il sboz tschernì",
    uncertain:
      "La stizzada n’ha betg pudì vegnir confermada. Emprova danovamain cun la medema versiun u rechargia per controllar sche il sboz exista anc.",
  },
};
