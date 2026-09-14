type Copy = {
  title: string;
  body: string;
  privacy: string;
  all: string;
  category: string;
  cancel: string;
  progress: string;
  complete: string;
  failed: string;
  scope: string;
};
export const monitoringExportCopy: Record<string, Copy> = {
  "en-CH": {
    title: "Download my monitor settings",
    body: "Download current configurations, revision numbers and email preferences for monitors you own in this workspace, including archived monitors. Records are collected and checked individually; this is not a historical archive or an import file.",
    privacy:
      "The JSON file can contain your private locations and interests. Connector credentials, source documents and colleagues’ monitors are excluded.",
    all: "Download all nine categories",
    category: "Download this category",
    cancel: "Cancel download",
    progress: "Collecting and checking settings",
    complete: "File prepared for download",
    failed:
      "Download could not be completed. Settings or access may have changed. Retry, or select one category for a smaller file.",
    scope: "Current category",
  },
  "de-CH": {
    title: "Meine Monitoring-Einstellungen herunterladen",
    body: "Aktuelle Konfigurationen, gespeicherte Revisionsnummern und E-Mail-Einstellungen Ihrer Monitore in diesem Arbeitsbereich herunterladen, einschließlich archivierter Monitore. Die Einträge werden einzeln gelesen und geprüft. Dies ist kein Verlaufsarchiv und keine Importdatei.",
    privacy:
      "Die JSON-Datei kann private Standorte und Interessen enthalten. Zugangsdaten, Quelldokumente und Monitore anderer Personen sind ausgeschlossen.",
    all: "Alle neun Kategorien herunterladen",
    category: "Diese Kategorie herunterladen",
    cancel: "Download abbrechen",
    progress: "Einstellungen werden gelesen und geprüft",
    complete: "Datei zum Herunterladen vorbereitet",
    failed:
      "Download nicht abgeschlossen. Einstellungen oder Zugriffsrechte könnten sich geändert haben. Erneut versuchen oder eine einzelne Kategorie für eine kleinere Datei wählen.",
    scope: "Aktuelle Kategorie",
  },
  "fr-CH": {
    title: "Télécharger mes paramètres de suivi",
    body: "Téléchargez les configurations actuelles, numéros de révision et préférences e-mail des suivis dont vous êtes propriétaire dans cet espace, y compris les suivis archivés. Chaque entrée est lue et vérifiée séparément. Ce fichier n’est ni un historique ni un fichier d’importation.",
    privacy:
      "Le fichier JSON peut contenir vos lieux et intérêts privés. Les identifiants de connexion, documents sources et suivis de collègues sont exclus.",
    all: "Télécharger les neuf catégories",
    category: "Télécharger cette catégorie",
    cancel: "Annuler le téléchargement",
    progress: "Lecture et vérification des paramètres",
    complete: "Fichier préparé pour le téléchargement",
    failed:
      "Téléchargement incomplet. Les paramètres ou droits d’accès ont peut-être changé. Réessayez ou choisissez une catégorie pour réduire la taille du fichier.",
    scope: "Catégorie actuelle",
  },
  "it-CH": {
    title: "Scarica le mie impostazioni di monitoraggio",
    body: "Scarica configurazioni attuali, numeri di revisione e preferenze e-mail dei monitor di tua proprietà in questo spazio, inclusi quelli archiviati. Ogni voce viene letta e verificata singolarmente. Il file non è un archivio storico né un file di importazione.",
    privacy:
      "Il file JSON può contenere luoghi e interessi privati. Credenziali, documenti delle fonti e monitor dei colleghi sono esclusi.",
    all: "Scarica tutte le nove categorie",
    category: "Scarica questa categoria",
    cancel: "Annulla download",
    progress: "Lettura e verifica delle impostazioni",
    complete: "File preparato per il download",
    failed:
      "Download non completato. Impostazioni o accessi potrebbero essere cambiati. Riprova o scegli una categoria per un file più piccolo.",
    scope: "Categoria attuale",
  },
  "rm-CH": {
    title: "Telechargiar mes parameters da surveglianza",
    body: "Telechargiai las configuraziuns actualas, ils numers da revisiun e las preferenzas dad e-mail da voss monitors en quest spazi da lavur, inclus ils monitors archivads. Mintga endataziun vegn legida e controllada separadamain. Quai n’è betg in archiv istoric u ina datoteca d’import.",
    privacy:
      "La datoteca JSON po cuntegnair voss lieus ed interess privats. Datas d’access, documents da funtauna e monitors da collegas èn exclus.",
    all: "Telechargiar tut las nov categorias",
    category: "Telechargiar questa categoria",
    cancel: "Interrumper il download",
    progress: "Leger e controllar ils parameters",
    complete: "Datoteca pronta per telechargiar",
    failed:
      "Il download n’ha betg pudì vegnir terminà. Parameters u dretgs d’access pon esser sa midads. Empruvai anc ina giada u tschernì ina categoria per ina datoteca pli pitschna.",
    scope: "Categoria actuala",
  },
};
