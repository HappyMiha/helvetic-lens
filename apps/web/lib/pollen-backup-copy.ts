import type { Locale } from "./i18n";

type Copy = {
  export: string;
  import: string;
  file: string;
  privacy: string;
  restore: string;
  busy: string;
  downloaded: string;
  invalid: string;
  unsupported: string;
  failed: string;
};
export const pollenBackupCopy: Record<Locale, Copy> = {
  "en-CH": {
    export: "Download settings backup",
    import: "Restore from a settings backup",
    file: "Choose a JSON backup (up to 64 KiB)",
    privacy:
      "The file contains your saved station, allergens, rules and delivery preferences. Keep it private. Unsaved edits, history and monitoring data are not included.",
    restore:
      "Review these imported settings, check them, then save a new private draft in this workspace. Existing drafts are unchanged. History, monitoring activation and email consent are not restored.",
    busy: "Preparing settings…",
    downloaded: "Settings download requested.",
    invalid:
      "This file could not be read. Choose a valid JSON settings backup of up to 64 KiB.",
    unsupported:
      "This backup format or configuration is not supported by this form. No settings were imported or downloaded.",
    failed:
      "The backup could not be prepared. Try again to recheck access and read the saved settings.",
  },
  "de-CH": {
    export: "Sicherung der Einstellungen herunterladen",
    import: "Einstellungen aus einer Sicherung wiederherstellen",
    file: "JSON-Sicherung wählen (bis 64 KiB)",
    privacy:
      "Die Datei enthält Ihre gespeicherte Station, Allergene, Regeln und Zustellpräferenzen. Bewahren Sie sie privat auf. Ungespeicherte Änderungen, Verlauf und Monitoring-Daten sind nicht enthalten.",
    restore:
      "Prüfen Sie diese importierten Einstellungen, lassen Sie sie validieren und speichern Sie einen neuen privaten Entwurf in diesem Arbeitsbereich. Bestehende Entwürfe bleiben unverändert. Verlauf, Monitoring-Aktivierung und E-Mail-Einwilligung werden nicht wiederhergestellt.",
    busy: "Einstellungen werden vorbereitet…",
    downloaded: "Download der Einstellungen angefordert.",
    invalid:
      "Diese Datei konnte nicht gelesen werden. Wählen Sie eine gültige JSON-Sicherung bis 64 KiB.",
    unsupported:
      "Dieses Sicherungsformat oder diese Konfiguration wird vom Formular nicht unterstützt. Es wurden keine Einstellungen importiert oder heruntergeladen.",
    failed:
      "Die Sicherung konnte nicht vorbereitet werden. Versuchen Sie es erneut, um den Zugriff zu prüfen und die gespeicherten Einstellungen zu laden.",
  },
  "fr-CH": {
    export: "Télécharger une sauvegarde des paramètres",
    import: "Restaurer les paramètres depuis une sauvegarde",
    file: "Choisir une sauvegarde JSON (64 Kio maximum)",
    privacy:
      "Le fichier contient votre station, vos allergènes, règles et préférences de réception enregistrés. Conservez-le de manière privée. Les modifications non enregistrées, l’historique et les données de suivi ne sont pas inclus.",
    restore:
      "Relisez ces paramètres importés, vérifiez-les, puis enregistrez un nouveau brouillon privé dans cet espace. Les brouillons existants restent inchangés. L’historique, l’activation du suivi et le consentement aux e-mails ne sont pas restaurés.",
    busy: "Préparation des paramètres…",
    downloaded: "Téléchargement des paramètres demandé.",
    invalid:
      "Ce fichier n’a pas pu être lu. Choisissez une sauvegarde JSON valide de 64 Kio maximum.",
    unsupported:
      "Ce format de sauvegarde ou cette configuration n’est pas pris en charge par ce formulaire. Aucun paramètre n’a été importé ou téléchargé.",
    failed:
      "La sauvegarde n’a pas pu être préparée. Réessayez pour vérifier l’accès et lire les paramètres enregistrés.",
  },
  "it-CH": {
    export: "Scarica una copia delle impostazioni",
    import: "Ripristina le impostazioni da una copia",
    file: "Scegli una copia JSON (massimo 64 KiB)",
    privacy:
      "Il file contiene la stazione, gli allergeni, le regole e le preferenze di recapito salvati. Conservalo in modo privato. Le modifiche non salvate, la cronologia e i dati di monitoraggio non sono inclusi.",
    restore:
      "Rivedi queste impostazioni importate, verificale e salva una nuova bozza privata in questo spazio. Le bozze esistenti restano invariate. Cronologia, attivazione del monitoraggio e consenso alle e-mail non vengono ripristinati.",
    busy: "Preparazione delle impostazioni…",
    downloaded: "Download delle impostazioni richiesto.",
    invalid:
      "Impossibile leggere questo file. Scegli una copia JSON valida di massimo 64 KiB.",
    unsupported:
      "Questo formato di copia o questa configurazione non è supportato dal modulo. Nessuna impostazione è stata importata o scaricata.",
    failed:
      "Impossibile preparare la copia. Riprova per verificare l’accesso e leggere le impostazioni salvate.",
  },
  "rm-CH": {
    export: "Telechargiar ina copia dals parameters",
    import: "Restaurar parameters d’ina copia",
    file: "Tscherner ina copia JSON (fin 64 KiB)",
    privacy:
      "La datoteca cuntegna tia staziun, allergens, reglas e preferenzas da spediziun memorisadas. Conserva ella privatamain. Midadas betg memorisadas, cronologia e datas da monitoring n’èn betg inclusas.",
    restore:
      "Controllescha quests parameters importads, lascha als validar e memorisescha in nov sboz privat en quest spazi. Ils sbozs existents restan senza midadas. Cronologia, activaziun dal monitoring e consentiment per e-mails na vegnan betg restaurads.",
    busy: "Preparar ils parameters…",
    downloaded: "Telechargiada dals parameters dumandada.",
    invalid:
      "Questa datoteca n’ha betg pudì vegnir legida. Tscherna ina copia JSON valida da maximalmain 64 KiB.",
    unsupported:
      "Quest format da copia u questa configuraziun na vegn betg sustegnì da quest formular. Nagins parameters èn vegnids importads u telechargiads.",
    failed:
      "La copia n’ha betg pudì vegnir preparada. Emprova danovamain per controllar l’access e leger ils parameters memorisads.",
  },
};
