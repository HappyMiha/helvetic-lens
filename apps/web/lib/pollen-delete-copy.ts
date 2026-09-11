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
    remove: "Delete monitor",
    confirm:
      "Delete the private monitor for station {station}, revision {revision}? Its settings, observations, reviews and delivery history will be removed. This cannot be undone.",
    busy: "Deleting monitor…",
    deleted: "The monitor and its private history were deleted.",
    conflict: "The monitor changed. Reload and review it before trying again.",
    reload: "Reload selected monitor",
    uncertain:
      "Deletion could not be confirmed. Retry the same revision or reload to check whether the monitor still exists.",
  },
  "de-CH": {
    remove: "Monitor löschen",
    confirm:
      "Den privaten Monitor für Station {station}, Version {revision}, löschen? Einstellungen, Beobachtungen, Prüfentscheide und Versanddaten werden entfernt. Dies kann nicht rückgängig gemacht werden.",
    busy: "Monitor wird gelöscht…",
    deleted: "Der Monitor und sein privater Verlauf wurden gelöscht.",
    conflict:
      "Der Monitor wurde geändert. Laden und prüfen Sie ihn vor einem erneuten Versuch.",
    reload: "Ausgewählten Monitor neu laden",
    uncertain:
      "Die Löschung konnte nicht bestätigt werden. Wiederholen Sie denselben Vorgang oder laden Sie neu, um zu prüfen, ob der Monitor noch existiert.",
  },
  "fr-CH": {
    remove: "Supprimer le suivi",
    confirm:
      "Supprimer le suivi privé de la station {station}, révision {revision} ? Ses paramètres, observations, décisions et données d’envoi seront supprimés. Cette action est irréversible.",
    busy: "Suppression du suivi…",
    deleted: "Le suivi et son historique privé ont été supprimés.",
    conflict:
      "Le suivi a changé. Rechargez-le et vérifiez-le avant de réessayer.",
    reload: "Recharger le suivi sélectionné",
    uncertain:
      "La suppression n’a pas pu être confirmée. Réessayez la même opération ou rechargez pour vérifier si le suivi existe encore.",
  },
  "it-CH": {
    remove: "Elimina monitoraggio",
    confirm:
      "Eliminare il monitoraggio privato della stazione {station}, revisione {revision}? Impostazioni, osservazioni, decisioni e dati di invio saranno eliminati. L’azione è irreversibile.",
    busy: "Eliminazione del monitoraggio…",
    deleted:
      "Il monitoraggio e la sua cronologia privata sono stati eliminati.",
    conflict:
      "Il monitoraggio è cambiato. Ricaricatelo e verificatelo prima di riprovare.",
    reload: "Ricarica monitoraggio selezionato",
    uncertain:
      "L’eliminazione non è stata confermata. Riprovate la stessa operazione o ricaricate per verificare se il monitoraggio esiste ancora.",
  },
  "rm-CH": {
    remove: "Stizzar il monitoring",
    confirm:
      "Stizzar il monitoring privat per la staziun {station}, versiun {revision}? Parameters, observaziuns, decisiuns e datas da spediziun vegnan stizzads. Quai na po betg vegnir revocà.",
    busy: "Stizzar il monitoring…",
    deleted: "Il monitoring e sia istorgia privata èn vegnids stizzads.",
    conflict:
      "Il monitoring è sa midà. Rechargia e controllescha el avant d’empruvar danovamain.",
    reload: "Rechargiar il monitoring tschernì",
    uncertain:
      "La stizzada n’ha betg pudì vegnir confermada. Emprova la medema operaziun u rechargia per controllar sche il monitoring exista anc.",
  },
};
