import type { Locale } from "./i18n";
type Copy = {
  cancel: string;
  edit: string;
  intro: string;
  unsupported: string;
  conflict: string;
  reload: string;
  discard: string;
  uncertain: string;
  recover: string;
  unchanged: string;
  recorded: string;
  saved: string;
};
export const pollenEditCopy: Record<Locale, Copy> = {
  "en-CH": {
    cancel: "Cancel editing",
    edit: "Edit draft",
    intro:
      "Edit the reviewed revision. Saved delivery preferences are preserved. Checking or saving settings does not start monitoring or send email.",
    unsupported:
      "These settings contain options this editor cannot safely change. They remain available for reading.",
    conflict:
      "A different revision exists or the draft is no longer editable. Reload and review before making another change.",
    reload: "Reload current settings",
    discard: "Discard these unsaved edits and read the current saved settings?",
    uncertain:
      "The update could not be confirmed. Check its saved result before retrying; the original revision and payload remain locked.",
    recover: "Check saved result",
    unchanged:
      "The original revision is still current. You may explicitly save again with that same expected revision.",
    recorded:
      "The requested settings are present in saved history. Open the draft to review its current settings.",
    saved:
      "A new configuration revision was saved. Monitoring has not started.",
  },
  "de-CH": {
    cancel: "Bearbeitung abbrechen",
    edit: "Entwurf bearbeiten",
    intro:
      "Bearbeiten Sie die geprüfte Version. Gespeicherte Versandpräferenzen bleiben erhalten. Prüfen oder Speichern startet keine Überwachung und versendet keine E-Mails.",
    unsupported:
      "Diese Einstellungen enthalten Optionen, die dieser Editor nicht sicher ändern kann. Sie bleiben lesbar.",
    conflict:
      "Eine andere Version existiert oder der Entwurf ist nicht mehr bearbeitbar. Laden Sie neu und prüfen Sie die Einstellungen vor einer weiteren Änderung.",
    reload: "Aktuelle Einstellungen neu laden",
    discard:
      "Diese ungespeicherten Änderungen verwerfen und die aktuellen Einstellungen lesen?",
    uncertain:
      "Die Änderung konnte nicht bestätigt werden. Prüfen Sie das gespeicherte Ergebnis vor einem erneuten Versuch; ursprüngliche Version und Anfrage bleiben gesperrt.",
    recover: "Gespeichertes Ergebnis prüfen",
    unchanged:
      "Die ursprüngliche Version ist noch aktuell. Sie können erneut mit derselben erwarteten Version speichern.",
    recorded:
      "Die gewünschten Einstellungen sind im gespeicherten Verlauf vorhanden. Öffnen Sie den Entwurf, um seine aktuellen Einstellungen zu prüfen.",
    saved:
      "Eine neue Einstellungsversion wurde gespeichert. Die Überwachung wurde nicht gestartet.",
  },
  "fr-CH": {
    cancel: "Annuler la modification",
    edit: "Modifier le brouillon",
    intro:
      "Modifiez la révision consultée. Les préférences d’envoi enregistrées sont conservées. Vérifier ou enregistrer ne démarre pas la surveillance et n’envoie pas d’e-mail.",
    unsupported:
      "Ces paramètres contiennent des options que cet éditeur ne peut pas modifier sans risque. Ils restent consultables.",
    conflict:
      "Une autre révision existe ou le brouillon n’est plus modifiable. Rechargez et vérifiez avant une nouvelle modification.",
    reload: "Recharger les paramètres actuels",
    discard:
      "Abandonner ces modifications non enregistrées et lire les paramètres actuels ?",
    uncertain:
      "La modification n’a pas pu être confirmée. Vérifiez le résultat enregistré avant de réessayer ; la révision et la requête initiales restent verrouillées.",
    recover: "Vérifier le résultat enregistré",
    unchanged:
      "La révision initiale est toujours actuelle. Vous pouvez enregistrer à nouveau avec cette même révision attendue.",
    recorded:
      "Les paramètres demandés figurent dans l’historique enregistré. Ouvrez le brouillon pour vérifier ses paramètres actuels.",
    saved:
      "Une nouvelle révision des paramètres a été enregistrée. La surveillance n’a pas démarré.",
  },
  "it-CH": {
    cancel: "Annulla modifica",
    edit: "Modifica bozza",
    intro:
      "Modificate la revisione consultata. Le preferenze di invio salvate vengono conservate. Verificare o salvare non avvia il monitoraggio e non invia e-mail.",
    unsupported:
      "Queste impostazioni contengono opzioni che l’editor non può modificare in sicurezza. Restano consultabili.",
    conflict:
      "Esiste un’altra revisione o la bozza non è più modificabile. Ricaricate e verificate prima di apportare altre modifiche.",
    reload: "Ricarica impostazioni attuali",
    discard:
      "Scartare queste modifiche non salvate e leggere le impostazioni attuali?",
    uncertain:
      "La modifica non è stata confermata. Verificate il risultato salvato prima di riprovare; revisione e richiesta originali restano bloccate.",
    recover: "Verifica risultato salvato",
    unchanged:
      "La revisione originale è ancora attuale. Potete salvare nuovamente con la stessa revisione attesa.",
    recorded:
      "Le impostazioni richieste sono presenti nella cronologia salvata. Aprite la bozza per verificarne le impostazioni attuali.",
    saved:
      "È stata salvata una nuova revisione delle impostazioni. Il monitoraggio non è stato avviato.",
  },
  "rm-CH": {
    cancel: "Interrumper la modificaziun",
    edit: "Modifitgar il sboz",
    intro:
      "Modifitgescha la versiun consultada. Las preferenzas da spediziun memorisadas restan mantegnidas. Verifitgar u memorisar na cumenza nagina surveglianza e na trametta nagins e-mails.",
    unsupported:
      "Quests parameters cuntegnan opziuns che quest editur na po betg midar cun segirezza. Els restan legibels.",
    conflict:
      "Ina autra versiun exista u il sboz na po betg pli vegnir modifitgà. Rechargia e controllescha avant ina nova midada.",
    reload: "Rechargiar ils parameters actuals",
    discard:
      "Sbittar questas midadas betg memorisadas e leger ils parameters actuals?",
    uncertain:
      "La midada n’ha betg pudì vegnir confermada. Controllescha il resultat memorisà avant d’empruvar danovamain; la versiun e la dumonda originalas restan bloccadas.",
    recover: "Controllar il resultat memorisà",
    unchanged:
      "La versiun originala è anc actuala. Ti pos memorisar danovamain cun la medema versiun spetgada.",
    recorded:
      "Ils parameters dumandads èn en l’istorgia memorisada. Avra il sboz per controllar ses parameters actuals.",
    saved:
      "Ina nova versiun dals parameters è vegnida memorisada. La surveglianza n’è betg cumenzada.",
  },
};
