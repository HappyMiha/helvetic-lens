import type { Locale } from "./i18n";

type Copy = {
  started: string; finished: string; body: string; all: string; details: string; close: string; previous: string; next: string;
  latest: string; retention: string; notes: string; generated: string; noNotes: string;
  previousRelease: string; activated: string; requested: string; unknown: string; host: string;
  truncated: string; compare: string; planned: string; statuses: Record<string, string>;
};
export const deploymentHistoryCopy: Record<Locale, Copy> = {
  "en-CH": {
    started: "Started", finished: "Finished",
    body: "Every recorded deployment attempt. Open a run for its phases, errors and pinned release notes. A Git push alone is not a deployment.",
    all: "All outcomes", details: "View deployment details", close: "Close details", previous: "Newer page", next: "Older page", latest: "Latest deployments",
    retention: "Older records may be missing from before the permanent journal was enabled. We do not reconstruct unrecorded deployments.",
    notes: "Release notes", generated: "Saved commit summary", noNotes: "No release notes were recorded for this attempt.",
    previousRelease: "Previous release", activated: "Verified activated commit", requested: "Requested commit", unknown: "Not recorded", host: "Host / environment",
    truncated: "Some diagnostics or changes exceed the display limit. This is not the complete output.", compare: "Open exact commit comparison", planned: "These were the intended changes. This attempt did not record a successful activation.",
    statuses: {succeeded:"Succeeded",failed:"Failed",deploying:"Deploying",running:"Running",interrupted:"Interrupted",rejected:"Rejected",rollback_failed:"Rollback failed"},
  },
  "de-CH": {
    started: "Beginn", finished: "Ende",
    body: "Alle aufgezeichneten Bereitstellungsversuche. Öffnen Sie einen Eintrag für Phasen, Fehler und gespeicherte Release Notes. Ein Git-Push ist noch keine Bereitstellung.",
    all: "Alle Ergebnisse", details: "Bereitstellungsdetails anzeigen", close: "Details schliessen", previous: "Neuere Seite", next: "Ältere Seite", latest: "Neueste Bereitstellungen",
    retention: "Vor der Aktivierung des dauerhaften Journals können ältere Einträge fehlen. Nicht aufgezeichnete Bereitstellungen werden nicht rekonstruiert.",
    notes: "Release Notes", generated: "Gespeicherte Commit-Zusammenfassung", noNotes: "Für diesen Versuch wurden keine Release Notes gespeichert.",
    previousRelease: "Vorherige Version", activated: "Verifiziert aktivierter Commit", requested: "Angeforderter Commit", unknown: "Nicht aufgezeichnet", host: "Host / Umgebung",
    truncated: "Einige Diagnosen oder Änderungen überschreiten die Anzeigegrenze. Dies ist nicht die vollständige Ausgabe.", compare: "Exakten Commit-Vergleich öffnen", planned: "Dies waren die vorgesehenen Änderungen. Für diesen Versuch wurde keine erfolgreiche Aktivierung aufgezeichnet.",
    statuses: {succeeded:"Erfolgreich",failed:"Fehlgeschlagen",deploying:"Wird bereitgestellt",running:"Läuft",interrupted:"Unterbrochen",rejected:"Abgelehnt",rollback_failed:"Rollback fehlgeschlagen"},
  },
  "fr-CH": {
    started: "Début", finished: "Fin",
    body: "Chaque tentative de déploiement enregistrée. Ouvrez une entrée pour voir les étapes, erreurs et notes de version sauvegardées. Un push Git n’est pas un déploiement.",
    all: "Tous les résultats", details: "Voir les détails du déploiement", close: "Fermer les détails", previous: "Page plus récente", next: "Page plus ancienne", latest: "Derniers déploiements",
    retention: "Des entrées antérieures à l’activation du journal permanent peuvent manquer. Nous ne reconstituons pas les déploiements non enregistrés.",
    notes: "Notes de version", generated: "Résumé des commits sauvegardé", noNotes: "Aucune note de version n’a été enregistrée pour cette tentative.",
    previousRelease: "Version précédente", activated: "Commit activé et vérifié", requested: "Commit demandé", unknown: "Non enregistré", host: "Hôte / environnement",
    truncated: "Certains diagnostics ou changements dépassent la limite d’affichage. Le résultat affiché est incomplet.", compare: "Ouvrir la comparaison exacte des commits", planned: "Il s’agissait des changements prévus. Cette tentative n’a pas enregistré d’activation réussie.",
    statuses: {succeeded:"Réussi",failed:"Échoué",deploying:"Déploiement en cours",running:"En cours",interrupted:"Interrompu",rejected:"Rejeté",rollback_failed:"Restauration échouée"},
  },
  "it-CH": {
    started: "Inizio", finished: "Fine",
    body: "Ogni tentativo di distribuzione registrato. Apri una voce per fasi, errori e note di rilascio salvate. Un push Git non è una distribuzione.",
    all: "Tutti gli esiti", details: "Visualizza i dettagli della distribuzione", close: "Chiudi i dettagli", previous: "Pagina più recente", next: "Pagina precedente", latest: "Ultime distribuzioni",
    retention: "Potrebbero mancare voci precedenti all’attivazione del registro permanente. Non ricostruiamo distribuzioni non registrate.",
    notes: "Note di rilascio", generated: "Riepilogo dei commit salvato", noNotes: "Non sono state registrate note di rilascio per questo tentativo.",
    previousRelease: "Versione precedente", activated: "Commit attivato e verificato", requested: "Commit richiesto", unknown: "Non registrato", host: "Host / ambiente",
    truncated: "Alcuni dati diagnostici o modifiche superano il limite di visualizzazione. Questo non è il risultato completo.", compare: "Apri il confronto esatto dei commit", planned: "Queste erano le modifiche previste. Questo tentativo non ha registrato un’attivazione riuscita.",
    statuses: {succeeded:"Riuscito",failed:"Fallito",deploying:"Distribuzione in corso",running:"In corso",interrupted:"Interrotto",rejected:"Rifiutato",rollback_failed:"Ripristino fallito"},
  },
  "rm-CH": {
    started: "Cumenzament", finished: "Fin",
    body: "Mintga emprova da publicaziun registrada. Avrai in element per las fasas, ils sbagls e las notas da versiun memorisadas. In push Git n’è betg ina publicaziun.",
    all: "Tut ils resultats", details: "Mussar ils detagls da publicaziun", close: "Serrar ils detagls", previous: "Pagina pli nova", next: "Pagina pli veglia", latest: "Las pli novas publicaziuns",
    retention: "Elements pli vegls pon mancar avant l’activaziun dal schurnal permanent. Nus na reconstruin betg publicaziuns betg registradas.",
    notes: "Notas da versiun", generated: "Resumaziun dals commits memorisada", noNotes: "Per questa emprova n’èn vegnidas registradas naginas notas da versiun.",
    previousRelease: "Versiun precedenta", activated: "Commit activà e verifitgà", requested: "Commit dumandà", unknown: "Betg registrà", host: "Host / ambient",
    truncated: "Intginas diagnosticas u midadas surpassan la limita da visualisaziun. Quai n’è betg il resultat cumplet.", compare: "Avrir la cumparegliaziun exacta dals commits", planned: "Quai eran las midadas previsas. Questa emprova n’ha betg registrà in’activaziun reussida.",
    statuses: {succeeded:"Reussì",failed:"Fallì",deploying:"Publicaziun en curs",running:"En curs",interrupted:"Interrut",rejected:"Refusà",rollback_failed:"Restabiliment fallì"},
  },
};
