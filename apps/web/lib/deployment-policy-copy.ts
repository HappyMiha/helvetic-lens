import type { Locale } from "./i18n";

type Copy = {
  title: string; body: string; default: string; next: string; useDefault: string;
  saveDefault: string; saveNext: string; cancel: string; reason: string;
  hotfix: string; effective: string; returnsTo: string; saved: string;
  saving: string; failed: string; conflict: string; reload: string; unavailable: string;
  sources: Record<string, string>; step: string;
};

export const deploymentPolicyCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Deployment mode", body: "Save a default for future releases or choose a mode for the next attempt only. The one-time choice is consumed when that attempt starts, even if it fails. An active deployment keeps its mode.",
    default: "Default mode", next: "Next attempt only", useDefault: "Use the default mode",
    saveDefault: "Save default", saveNext: "Save next mode", cancel: "Cancel next override",
    reason: "Hotfix reason (10–500 characters, no secrets)",
    hotfix: "Hotfix skips API and web tests. Build, backup, readiness checks and rollback still apply. A hotfix default skips tests on every release until you change it.",
    effective: "Next deployment", returnsTo: "Following deployments", saved: "Deployment mode saved.",
    saving: "Saving…", failed: "Could not save deployment settings. Retry after reloading.",
    conflict: "Settings changed in another tab or the next mode was consumed. Reload the saved settings before choosing again.",
    reload: "Reload saved settings", unavailable: "Deployment mode settings are unavailable on this host.",
    sources: { default: "Saved default", next: "Next attempt only", invocation: "Explicit host invocation", bootstrap: "First installation" }, step: "Select deployment mode",
  },
  "de-CH": {
    title: "Deployment-Modus", body: "Speichern Sie einen Standard für künftige Releases oder wählen Sie einen Modus nur für den nächsten Versuch. Die einmalige Auswahl wird beim Start verbraucht, auch wenn der Versuch fehlschlägt. Ein laufendes Deployment behält seinen Modus.",
    default: "Standardmodus", next: "Nur nächster Versuch", useDefault: "Standardmodus verwenden",
    saveDefault: "Standard speichern", saveNext: "Nächsten Modus speichern", cancel: "Einmalige Auswahl aufheben",
    reason: "Hotfix-Begründung (10–500 Zeichen, keine Geheimnisse)",
    hotfix: "Hotfix überspringt API- und Webtests. Build, Sicherung, Betriebsprüfung und Rollback bleiben aktiv. Ein Hotfix als Standard überspringt Tests bei jedem Release, bis Sie ihn ändern.",
    effective: "Nächstes Deployment", returnsTo: "Darauffolgende Deployments", saved: "Deployment-Modus gespeichert.",
    saving: "Wird gespeichert…", failed: "Deployment-Einstellungen konnten nicht gespeichert werden. Laden Sie sie erneut und versuchen Sie es nochmals.",
    conflict: "Die Einstellungen wurden in einem anderen Tab geändert oder die einmalige Auswahl wurde verbraucht. Laden Sie die gespeicherten Einstellungen vor einer neuen Auswahl.",
    reload: "Gespeicherte Einstellungen laden", unavailable: "Deployment-Einstellungen sind auf diesem Host nicht verfügbar.",
    sources: { default: "Gespeicherter Standard", next: "Nur nächster Versuch", invocation: "Expliziter Host-Aufruf", bootstrap: "Erstinstallation" }, step: "Deployment-Modus wählen",
  },
  "fr-CH": {
    title: "Mode de déploiement", body: "Enregistrez un mode par défaut ou choisissez un mode pour la prochaine tentative uniquement. Le choix ponctuel est consommé au démarrage, même en cas d’échec. Un déploiement en cours conserve son mode.",
    default: "Mode par défaut", next: "Prochaine tentative uniquement", useDefault: "Utiliser le mode par défaut",
    saveDefault: "Enregistrer le mode par défaut", saveNext: "Enregistrer le prochain mode", cancel: "Annuler le choix ponctuel",
    reason: "Motif du correctif urgent (10–500 caractères, sans secrets)",
    hotfix: "Le correctif urgent ignore les tests API et web. La compilation, la sauvegarde, les vérifications et le retour arrière restent actifs. Ce mode par défaut ignore les tests à chaque version jusqu’à sa modification.",
    effective: "Prochain déploiement", returnsTo: "Déploiements suivants", saved: "Mode de déploiement enregistré.",
    saving: "Enregistrement…", failed: "Impossible d’enregistrer les paramètres. Rechargez-les puis réessayez.",
    conflict: "Les paramètres ont changé dans un autre onglet ou le choix ponctuel a été consommé. Rechargez les paramètres enregistrés avant de choisir à nouveau.",
    reload: "Recharger les paramètres enregistrés", unavailable: "Les paramètres de déploiement sont indisponibles sur cet hôte.",
    sources: { default: "Mode par défaut enregistré", next: "Prochaine tentative uniquement", invocation: "Commande explicite sur l’hôte", bootstrap: "Première installation" }, step: "Choisir le mode de déploiement",
  },
  "it-CH": {
    title: "Modalità di distribuzione", body: "Salva una modalità predefinita o scegline una solo per il prossimo tentativo. La scelta singola viene utilizzata all’avvio, anche in caso di errore. Una distribuzione in corso mantiene la propria modalità.",
    default: "Modalità predefinita", next: "Solo il prossimo tentativo", useDefault: "Usa la modalità predefinita",
    saveDefault: "Salva modalità predefinita", saveNext: "Salva prossima modalità", cancel: "Annulla scelta singola",
    reason: "Motivo della correzione urgente (10–500 caratteri, senza segreti)",
    hotfix: "La correzione urgente salta i test API e web. Compilazione, backup, verifiche e ripristino restano attivi. Se predefinita, salta i test a ogni versione fino alla modifica.",
    effective: "Prossima distribuzione", returnsTo: "Distribuzioni successive", saved: "Modalità di distribuzione salvata.",
    saving: "Salvataggio…", failed: "Impossibile salvare le impostazioni. Ricaricale e riprova.",
    conflict: "Le impostazioni sono cambiate in un’altra scheda o la scelta singola è stata utilizzata. Ricarica le impostazioni salvate prima di scegliere di nuovo.",
    reload: "Ricarica impostazioni salvate", unavailable: "Le impostazioni di distribuzione non sono disponibili su questo host.",
    sources: { default: "Modalità predefinita salvata", next: "Solo il prossimo tentativo", invocation: "Comando esplicito sull’host", bootstrap: "Prima installazione" }, step: "Scegli modalità di distribuzione",
  },
  "rm-CH": {
    title: "Modus da publicaziun", body: "Memorisai in modus da standard u tschernì in modus mo per la proxima emprova. La tscherna unica vegn duvrada al cumenzament, er sche l’emprova na reussescha betg. Ina publicaziun activa mantegna ses modus.",
    default: "Modus da standard", next: "Mo la proxima emprova", useDefault: "Duvrar il modus da standard",
    saveDefault: "Memorisar il standard", saveNext: "Memorisar il proxim modus", cancel: "Annullar la tscherna unica",
    reason: "Motiv da la correctura urgenta (10–500 caracters, senza secrets)",
    hotfix: "La correctura urgenta ometta ils tests API e web. Compilaziun, copia da segirezza, controllas e restauraziun restan activas. Sco standard ometta ella ils tests da mintga versiun fin che Vus midais il modus.",
    effective: "Proxima publicaziun", returnsTo: "Publicaziuns suandantas", saved: "Modus da publicaziun memorisà.",
    saving: "Memorisar…", failed: "Impussibel da memorisar ils parameters. Chargiai els danovamain e repetì.",
    conflict: "Ils parameters èn vegnids midads en in auter tab u la tscherna unica è vegnida duvrada. Chargiai ils parameters memorisads avant da tscherner danovamain.",
    reload: "Chargiar ils parameters memorisads", unavailable: "Ils parameters da publicaziun n’èn betg disponibels sin quest host.",
    sources: { default: "Standard memorisà", next: "Mo la proxima emprova", invocation: "Cumond explicit sin il host", bootstrap: "Emprima installaziun" }, step: "Tscherner il modus da publicaziun",
  },
};
