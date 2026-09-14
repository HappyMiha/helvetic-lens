import type { Locale } from "./i18n";

const en = {
  title: "Account and privacy",
  intro:
    "Review your personal data and workspace responsibilities before deleting your account.",
  export: "Download monitoring settings",
  preview: "Review account deletion",
  cancel: "Cancel preview",
  busy: "Checking your account…",
  monitors: "Owned monitors",
  workspaces: "Workspaces",
  records: "Other personal settings and history",
  conversations: "Conversations",
  sessions: "Sign-in sessions",
  documents: "Private document versions",
  remove: "Delete my account",
  password: "Current password",
  confirm:
    "I understand that my account, personal monitors, preferences and conversations will be permanently removed.",
  workspaceConfirm:
    "I also agree to erase the private workspaces marked for deletion, including their documents and settings.",
  retained:
    "Official source data, colleagues’ private data and shared decisions remain. Shared decisions lose the account link; free-text notes remain workspace records. Platform source credentials are retained.",
  files:
    "Unreferenced files enter the existing cleanup process: {hours} hours of file retention, with cleanup scheduled every 24 hours. Backups, previously delivered messages and retained source documents are not erased immediately.",
  failed:
    "The result could not be confirmed. Reload the preview or sign in again before continuing.",
  passwordError: "The password is incorrect. Reload the preview and try again.",
  deleted:
    "Your account has been deleted. Shared records and retained copies follow the retention limits shown before deletion.",
  open: "Open this workspace",
  monitor: "Open monitor ownership",
  leave: "Leave workspace",
  erase: "Erase private workspace",
  blocked: "Resolve before deletion",
  workspace_administrator:
    "Another active administrator must take responsibility for this workspace.",
  platform_administrator:
    "Promote another active platform administrator before deleting this account.",
  monitor_owner:
    "Transfer this shared monitor to another active workspace administrator first.",
  workspace_private_data:
    "A former member’s private data remains in this workspace and needs review before workspace erasure.",
  retained_workspace_reference:
    "Another workspace still depends on private evidence selected for erasure. Resolve that dependency first.",
  membership:
    "Restore membership through the workspace administrator to complete the ownership handover.",
};
export const accountCopy: Record<Locale, Record<keyof typeof en, string>> = {
  "en-CH": en,
  "de-CH": {
    title: "Konto und Datenschutz",
    intro:
      "Prüfen Sie persönliche Daten und Verantwortlichkeiten, bevor Sie Ihr Konto löschen.",
    export: "Überwachungseinstellungen herunterladen",
    preview: "Kontolöschung prüfen",
    cancel: "Vorschau abbrechen",
    busy: "Konto wird geprüft…",
    monitors: "Eigene Überwachungen",
    workspaces: "Arbeitsbereiche",
    records: "Weitere persönliche Einstellungen und Verläufe",
    conversations: "Gespräche",
    sessions: "Anmeldesitzungen",
    documents: "Private Dokumentversionen",
    remove: "Mein Konto löschen",
    password: "Aktuelles Passwort",
    confirm:
      "Ich verstehe, dass mein Konto, persönliche Überwachungen, Einstellungen und Gespräche dauerhaft gelöscht werden.",
    workspaceConfirm:
      "Ich stimme auch der Löschung der markierten privaten Arbeitsbereiche einschliesslich ihrer Dokumente und Einstellungen zu.",
    retained:
      "Offizielle Quelldaten, private Daten anderer Personen und geteilte Entscheidungen bleiben erhalten. Bei geteilten Entscheidungen entfällt der Kontobezug; Freitextnotizen bleiben Arbeitsbereichsdaten. Plattform-Zugangsdaten für Quellen bleiben erhalten.",
    files:
      "Nicht mehr referenzierte Dateien werden durch die bestehende Bereinigung entfernt: {hours} Stunden Dateiaufbewahrung, Bereinigung alle 24 Stunden. Backups, bereits versandte Nachrichten und aufbewahrte Quelldokumente werden nicht sofort gelöscht.",
    failed:
      "Das Ergebnis konnte nicht bestätigt werden. Laden Sie die Vorschau neu oder melden Sie sich erneut an.",
    passwordError:
      "Das Passwort ist falsch. Laden Sie die Vorschau neu und versuchen Sie es erneut.",
    deleted:
      "Ihr Konto wurde gelöscht. Geteilte Aufzeichnungen und aufbewahrte Kopien unterliegen weiterhin den zuvor angezeigten Aufbewahrungsgrenzen.",
    open: "Diesen Arbeitsbereich öffnen",
    monitor: "Eigentum der Überwachung öffnen",
    leave: "Arbeitsbereich verlassen",
    erase: "Privaten Arbeitsbereich löschen",
    blocked: "Vor der Löschung klären",
    workspace_administrator:
      "Eine andere aktive Administration muss diesen Arbeitsbereich übernehmen.",
    platform_administrator:
      "Ernennen Sie vor der Kontolöschung eine andere aktive Plattformadministration.",
    monitor_owner:
      "Übertragen Sie diese geteilte Überwachung zuerst an eine andere aktive Administration des Arbeitsbereichs.",
    workspace_private_data:
      "Private Daten eines früheren Mitglieds sind noch vorhanden und müssen vor der Löschung des Arbeitsbereichs geprüft werden.",
    retained_workspace_reference:
      "Ein anderer Arbeitsbereich benötigt noch private Belege, die gelöscht würden. Klären Sie zuerst diese Abhängigkeit.",
    membership:
      "Lassen Sie die Mitgliedschaft durch die Administration wiederherstellen, um die Eigentumsübergabe abzuschliessen.",
  },
  "fr-CH": {
    title: "Compte et confidentialité",
    intro:
      "Vérifiez vos données personnelles et vos responsabilités avant de supprimer votre compte.",
    export: "Télécharger les paramètres de suivi",
    preview: "Examiner la suppression du compte",
    cancel: "Annuler l’aperçu",
    busy: "Vérification du compte…",
    monitors: "Mes suivis",
    workspaces: "Espaces de travail",
    records: "Autres paramètres et historiques personnels",
    conversations: "Conversations",
    sessions: "Sessions de connexion",
    documents: "Versions de documents privés",
    remove: "Supprimer mon compte",
    password: "Mot de passe actuel",
    confirm:
      "Je comprends que mon compte, mes suivis personnels, mes préférences et mes conversations seront définitivement supprimés.",
    workspaceConfirm:
      "J’accepte aussi de supprimer les espaces privés indiqués, y compris leurs documents et paramètres.",
    retained:
      "Les données officielles, les données privées des collègues et les décisions partagées sont conservées. Le lien au compte disparaît des décisions partagées ; les notes libres restent des données de l’espace. Les identifiants des sources de la plateforme sont conservés.",
    files:
      "Les fichiers sans référence suivent le nettoyage existant : conservation de {hours} heures et nettoyage programmé toutes les 24 heures. Les sauvegardes, messages déjà envoyés et documents sources conservés ne sont pas effacés immédiatement.",
    failed:
      "Le résultat n’a pas pu être confirmé. Rechargez l’aperçu ou reconnectez-vous avant de continuer.",
    passwordError:
      "Le mot de passe est incorrect. Rechargez l’aperçu et réessayez.",
    deleted:
      "Votre compte a été supprimé. Les données partagées et les copies conservées suivent les limites de conservation affichées avant la suppression.",
    open: "Ouvrir cet espace",
    monitor: "Ouvrir la propriété du suivi",
    leave: "Quitter l’espace",
    erase: "Supprimer l’espace privé",
    blocked: "À résoudre avant la suppression",
    workspace_administrator:
      "Un autre administrateur actif doit reprendre la responsabilité de cet espace.",
    platform_administrator:
      "Nommez un autre administrateur actif de la plateforme avant de supprimer ce compte.",
    monitor_owner:
      "Transférez d’abord ce suivi partagé à un autre administrateur actif de l’espace.",
    workspace_private_data:
      "Des données privées d’un ancien membre restent dans cet espace et doivent être examinées avant sa suppression.",
    retained_workspace_reference:
      "Un autre espace dépend encore de preuves privées sélectionnées pour la suppression. Résolvez cette dépendance.",
    membership:
      "Demandez à l’administrateur de rétablir votre appartenance pour terminer le transfert de propriété.",
  },
  "it-CH": {
    title: "Account e privacy",
    intro:
      "Controlla i tuoi dati personali e le responsabilità prima di eliminare l’account.",
    export: "Scarica le impostazioni di monitoraggio",
    preview: "Controlla l’eliminazione dell’account",
    cancel: "Annulla anteprima",
    busy: "Controllo dell’account…",
    monitors: "Monitoraggi di mia proprietà",
    workspaces: "Spazi di lavoro",
    records: "Altre impostazioni e cronologie personali",
    conversations: "Conversazioni",
    sessions: "Sessioni di accesso",
    documents: "Versioni di documenti privati",
    remove: "Elimina il mio account",
    password: "Password attuale",
    confirm:
      "Comprendo che il mio account, i monitoraggi personali, le preferenze e le conversazioni verranno eliminati definitivamente.",
    workspaceConfirm:
      "Acconsento anche a eliminare gli spazi privati indicati, inclusi documenti e impostazioni.",
    retained:
      "I dati ufficiali, i dati privati dei colleghi e le decisioni condivise restano disponibili. Il collegamento all’account viene rimosso dalle decisioni condivise; le note libere restano dati dello spazio. Le credenziali delle fonti della piattaforma vengono conservate.",
    files:
      "I file senza riferimenti seguono la pulizia esistente: conservazione di {hours} ore e pulizia programmata ogni 24 ore. Backup, messaggi già inviati e documenti delle fonti conservati non vengono cancellati subito.",
    failed:
      "Impossibile confermare il risultato. Ricarica l’anteprima o accedi nuovamente prima di continuare.",
    passwordError: "La password è errata. Ricarica l’anteprima e riprova.",
    deleted:
      "Il tuo account è stato eliminato. I dati condivisi e le copie conservate seguono i limiti di conservazione mostrati prima dell’eliminazione.",
    open: "Apri questo spazio",
    monitor: "Apri la proprietà del monitoraggio",
    leave: "Lascia lo spazio",
    erase: "Elimina lo spazio privato",
    blocked: "Da risolvere prima dell’eliminazione",
    workspace_administrator:
      "Un altro amministratore attivo deve assumere la responsabilità di questo spazio.",
    platform_administrator:
      "Nomina un altro amministratore attivo della piattaforma prima di eliminare l’account.",
    monitor_owner:
      "Trasferisci prima il monitoraggio condiviso a un altro amministratore attivo dello spazio.",
    workspace_private_data:
      "In questo spazio restano dati privati di un ex membro, da esaminare prima di eliminare lo spazio.",
    retained_workspace_reference:
      "Un altro spazio dipende ancora da prove private selezionate per l’eliminazione. Risolvi prima questa dipendenza.",
    membership:
      "Chiedi all’amministratore di ripristinare l’appartenenza per completare il trasferimento di proprietà.",
  },
  "rm-CH": {
    title: "Conto e protecziun da datas",
    intro:
      "Controllai las datas persunalas e las responsabladads avant da stizzar il conto.",
    export: "Telechargiar ils parameters da surveglianza",
    preview: "Examinar la stizzada dal conto",
    cancel: "Interrumper la prevista",
    busy: "Controllar il conto…",
    monitors: "Atgnas surveglianzas",
    workspaces: "Spazis da lavur",
    records: "Auters parameters ed istorgias persunals",
    conversations: "Discurs",
    sessions: "Sessiuns d’annunzia",
    documents: "Versiuns da documents privats",
    remove: "Stizzar mes conto",
    password: "Pled-clav actual",
    confirm:
      "Jau chapesch che mes conto, mias surveglianzas persunalas, preferenzas e mes discurs vegnan stizzads definitivamain.",
    workspaceConfirm:
      "Jau sun era d’accord da stizzar ils spazis privats marcads, inclus lur documents e parameters.",
    retained:
      "Datas uffizialas, datas privatas da collegas e decisiuns partidas restan. La colliaziun al conto vegn allontanada da decisiuns partidas; notas libras restan datas dal spazi. Las credenzialas da funtaunas da la plattafurma vegnan mantegnidas.",
    files:
      "Datotecas senza referenzas suondan la nettegiada existenta: conservaziun da {hours} uras e nettegiada planisada mintga 24 uras. Copias da segirezza, messadis gia tramess e documents da funtaunas conservads na vegnan betg stizzads immediatamain.",
    failed:
      "Il resultat n’ha betg pudì vegnir confermà. Rechargiai la prevista u As annunziai danovamain avant da cuntinuar.",
    passwordError:
      "Il pled-clav n’è betg correct. Rechargiai la prevista ed empruvai anc ina giada.",
    deleted:
      "Voss conto è vegnì stizzà. Datas partidas e copias conservadas suondan ils limits da conservaziun mussads avant la stizzada.",
    open: "Avrir quest spazi",
    monitor: "Avrir la proprietad da la surveglianza",
    leave: "Bandunar il spazi",
    erase: "Stizzar il spazi privat",
    blocked: "Sclerir avant la stizzada",
    workspace_administrator:
      "In auter administratur activ sto surpigliar la responsabladad per quest spazi.",
    platform_administrator:
      "Numnai in auter administratur activ da la plattafurma avant da stizzar quest conto.",
    monitor_owner:
      "Transferi l’emprim questa surveglianza partida ad in auter administratur activ dal spazi.",
    workspace_private_data:
      "Datas privatas d’in anteriur commember restan en quest spazi e ston vegnir examinadas avant la stizzada dal spazi.",
    retained_workspace_reference:
      "In auter spazi dependa anc da cumprovas privatas tschernidas per la stizzada. Sclerì l’emprim questa dependenza.",
    membership:
      "Laschai restabilir la commembranza tras l’administratur per terminar la transferenza da proprietad.",
  },
};
