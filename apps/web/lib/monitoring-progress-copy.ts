import type { Locale } from "./i18n";

type TaskStatus = "PLANNED" | "READY" | "IN PROGRESS" | "VERIFYING" | "DONE" | "BLOCKED" | "DEFERRED";

type Copy = {
  title: string;
  git: string;
  gitStatus: string;
  deployed: string;
  deployedStatus: string;
  verified: string;
  remaining: string;
  completed: string;
  inProgress: string;
  unavailable: string;
  notApplicable: string;
  noRequired: string;
  absent: string;
  unknownTitle: string;
  source: string;
  updated: string;
  note: string;
  mvpNote: string;
  deployedNote: string;
  verifiedNote: string;
  missingNote: string;
  pollen: string;
  pollenNote: string;
  viewSteps: string;
  unfinished: string;
  awaiting: string;
  noneRemaining: string;
  noneAwaiting: string;
  statuses: Record<TaskStatus, string>;
};

export const monitoringProgressCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Monitoring v2 progress",
    git: "Completed in Git",
    gitStatus: "In Git",
    deployed: "Already on this site",
    deployedStatus: "On this site",
    verified: "Last verified release",
    remaining: "Remaining",
    completed: "tasks complete",
    inProgress: "in progress",
    unavailable: "Unavailable",
    notApplicable: "Not applicable",
    noRequired: "No required tasks in this revision.",
    absent: "Not present in this revision",
    unknownTitle: "Task title unavailable",
    source: "Backlog revision",
    updated: "Observed",
    note: "Tasks differ in size; each required task counts equally. Deferred work is excluded.",
    mvpNote: "Progress starts from the frozen MVP baseline.",
    deployedNote: "Completion recorded in this deployed revision.",
    verifiedNote: "Completion recorded in the last verified release. Deployment is still in progress.",
    missingNote: "Progress metadata is unavailable for this instance.",
    pollen: "Pollen Watch — first delivery",
    pollenNote: "Six tasks through the real-user testing gate (MV2-071).",
    viewSteps: "View six steps",
    unfinished: "Unfinished required tasks",
    awaiting: "Completed in Git, awaiting deployment",
    noneRemaining: "No unfinished required tasks in this revision.",
    noneAwaiting: "No completed tasks are awaiting deployment.",
    statuses: {
      PLANNED: "Planned", READY: "Ready", "IN PROGRESS": "In progress", VERIFYING: "Verifying",
      DONE: "Done", BLOCKED: "Blocked", DEFERRED: "Deferred",
    },
  },
  "de-CH": {
    title: "Fortschritt von Monitoring v2",
    git: "In Git abgeschlossen",
    gitStatus: "In Git",
    deployed: "Bereits auf dieser Website",
    deployedStatus: "Auf dieser Website",
    verified: "Zuletzt verifizierte Version",
    remaining: "Noch offen",
    completed: "Aufgaben abgeschlossen",
    inProgress: "in Bearbeitung",
    unavailable: "Nicht verfügbar",
    notApplicable: "Nicht anwendbar",
    noRequired: "Diese Revision enthält keine erforderlichen Aufgaben.",
    absent: "In dieser Revision nicht enthalten",
    unknownTitle: "Aufgabentitel nicht verfügbar",
    source: "Revision des Aufgabenplans",
    updated: "Erfasst",
    note: "Aufgaben sind unterschiedlich gross; jede erforderliche Aufgabe zählt gleich. Zurückgestellte Arbeiten sind ausgeschlossen.",
    mvpNote: "Der Fortschritt beginnt beim eingefrorenen MVP-Stand.",
    deployedNote: "In dieser bereitgestellten Revision als abgeschlossen erfasst.",
    verifiedNote: "In der zuletzt verifizierten Version als abgeschlossen erfasst. Die Bereitstellung läuft noch.",
    missingNote: "Für diese Instanz sind keine Fortschrittsdaten verfügbar.",
    pollen: "Pollen Watch — erste Lieferung",
    pollenNote: "Sechs Aufgaben bis zur Freigabe für Tests mit echten Nutzenden (MV2-071).",
    viewSteps: "Sechs Schritte anzeigen",
    unfinished: "Offene erforderliche Aufgaben",
    awaiting: "In Git abgeschlossen, Bereitstellung ausstehend",
    noneRemaining: "In dieser Revision sind keine erforderlichen Aufgaben mehr offen.",
    noneAwaiting: "Keine abgeschlossenen Aufgaben warten auf die Bereitstellung.",
    statuses: {
      PLANNED: "Geplant", READY: "Bereit", "IN PROGRESS": "In Bearbeitung", VERIFYING: "In Prüfung",
      DONE: "Erledigt", BLOCKED: "Blockiert", DEFERRED: "Zurückgestellt",
    },
  },
  "fr-CH": {
    title: "Avancement de Monitoring v2",
    git: "Terminé dans Git",
    gitStatus: "Dans Git",
    deployed: "Déjà sur ce site",
    deployedStatus: "Sur ce site",
    verified: "Dernière version vérifiée",
    remaining: "À terminer",
    completed: "tâches terminées",
    inProgress: "en cours",
    unavailable: "Indisponible",
    notApplicable: "Sans objet",
    noRequired: "Aucune tâche requise dans cette révision.",
    absent: "Absent de cette révision",
    unknownTitle: "Titre de la tâche indisponible",
    source: "Révision de la liste des tâches",
    updated: "Observé",
    note: "Les tâches varient en taille ; chaque tâche requise compte autant. Les travaux différés sont exclus.",
    mvpNote: "Le progrès part de la version figée du MVP.",
    deployedNote: "Achèvement enregistré dans cette révision déployée.",
    verifiedNote: "Achèvement enregistré dans la dernière version vérifiée. Le déploiement est encore en cours.",
    missingNote: "Les données d’avancement sont indisponibles pour cette instance.",
    pollen: "Pollen Watch — première livraison",
    pollenNote: "Six tâches jusqu’à la validation des tests avec de vrais utilisateurs (MV2-071).",
    viewSteps: "Voir les six étapes",
    unfinished: "Tâches requises à terminer",
    awaiting: "Terminé dans Git, en attente de déploiement",
    noneRemaining: "Aucune tâche requise ne reste à terminer dans cette révision.",
    noneAwaiting: "Aucune tâche terminée n’attend son déploiement.",
    statuses: {
      PLANNED: "Planifié", READY: "Prêt", "IN PROGRESS": "En cours", VERIFYING: "En vérification",
      DONE: "Terminé", BLOCKED: "Bloqué", DEFERRED: "Différé",
    },
  },
  "it-CH": {
    title: "Avanzamento di Monitoring v2",
    git: "Completato in Git",
    gitStatus: "In Git",
    deployed: "Già su questo sito",
    deployedStatus: "Su questo sito",
    verified: "Ultima versione verificata",
    remaining: "Da completare",
    completed: "attività completate",
    inProgress: "in corso",
    unavailable: "Non disponibile",
    notApplicable: "Non applicabile",
    noRequired: "Nessuna attività obbligatoria in questa revisione.",
    absent: "Non presente in questa revisione",
    unknownTitle: "Titolo dell’attività non disponibile",
    source: "Revisione dell’elenco delle attività",
    updated: "Rilevato",
    note: "Le attività hanno dimensioni diverse; ogni attività obbligatoria conta allo stesso modo. I lavori rinviati sono esclusi.",
    mvpNote: "L’avanzamento parte dalla versione congelata del MVP.",
    deployedNote: "Completamento registrato in questa revisione distribuita.",
    verifiedNote: "Completamento registrato nell’ultima versione verificata. La distribuzione è ancora in corso.",
    missingNote: "I dati di avanzamento non sono disponibili per questa istanza.",
    pollen: "Pollen Watch — prima consegna",
    pollenNote: "Sei attività fino alla verifica per i test con utenti reali (MV2-071).",
    viewSteps: "Mostra i sei passaggi",
    unfinished: "Attività obbligatorie da completare",
    awaiting: "Completato in Git, in attesa di distribuzione",
    noneRemaining: "Non restano attività obbligatorie da completare in questa revisione.",
    noneAwaiting: "Nessuna attività completata è in attesa di distribuzione.",
    statuses: {
      PLANNED: "Pianificato", READY: "Pronto", "IN PROGRESS": "In corso", VERIFYING: "In verifica",
      DONE: "Completato", BLOCKED: "Bloccato", DEFERRED: "Rinviato",
    },
  },
  "rm-CH": {
    title: "Progress da Monitoring v2",
    git: "Terminà en Git",
    gitStatus: "En Git",
    deployed: "Gia sin questa pagina",
    deployedStatus: "Sin questa pagina",
    verified: "Ultima versiun verifitgada",
    remaining: "Anc avert",
    completed: "incumbensas terminadas",
    inProgress: "en lavur",
    unavailable: "Betg disponibel",
    notApplicable: "Betg applitgabel",
    noRequired: "Naginas incumbensas necessarias en questa revisiun.",
    absent: "Betg cuntegnì en questa revisiun",
    unknownTitle: "Titel da l’incumbensa betg disponibel",
    source: "Revisiun da la glista d’incumbensas",
    updated: "Observà",
    note: "Las incumbensas èn da grondezza differenta; mintga incumbensa necessaria quinta tuttina. Lavurs remessas èn exclusas.",
    mvpNote: "Il progress parta dal stadi fixà dal MVP.",
    deployedNote: "Terminaziun registrada en questa revisiun publitgada.",
    verifiedNote: "Terminaziun registrada en l’ultima versiun verifitgada. La publicaziun è anc en curs.",
    missingNote: "Las datas dal progress n’èn betg disponiblas per questa instanza.",
    pollen: "Pollen Watch — emprima furniziun",
    pollenNote: "Sis incumbensas fin a la verificaziun per tests cun utilisaders reals (MV2-071).",
    viewSteps: "Mussar ils sis pass",
    unfinished: "Incumbensas necessarias anc avertas",
    awaiting: "Terminà en Git, en spetga da publicaziun",
    noneRemaining: "Naginas incumbensas necessarias èn anc avertas en questa revisiun.",
    noneAwaiting: "Naginas incumbensas terminadas spetgan la publicaziun.",
    statuses: {
      PLANNED: "Planisà", READY: "Pront", "IN PROGRESS": "En lavur", VERIFYING: "En verificaziun",
      DONE: "Terminà", BLOCKED: "Bloccà", DEFERRED: "Remess",
    },
  },
};
