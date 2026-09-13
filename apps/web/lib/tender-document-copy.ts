import type { Locale } from "./i18n";

const en = {
  qa: "Questions and answers",
  title: "Tender documents",
  files: "Retained originals",
  set: "Saved document set",
  help: "Only permitted saved evidence is shown. Text extraction does not cover diagrams or scanned content. Original files remain authoritative.",
  none: "No readable saved documents in this selection. This does not prove that the source has no documents.",
  open: "Read saved text",
  download: "Download original file",
  compare: "Compare saved versions",
  before: "Before",
  after: "After",
  page: "Page",
  location: "Source location",
  partial:
    "Text extraction is incomplete. Review the original file for missing information.",
  failed:
    "No verified text extraction is available. The original file may still be readable in a suitable application.",
  unchanged:
    "No text difference was found after whitespace normalization. The file bytes may still differ.",
  truncated:
    "This is a bounded extract. Download both originals for the full evidence.",
  unavailable:
    "Evidence is unavailable. Access or retention may have changed. Refresh to check again.",
  literal:
    "These are literal text differences, not an interpretation of procurement requirements.",
  withdrawn: "Withdrawn",
  removed: "Removed from the source listing",
  incompleteSet: "The source listing was incomplete.",
};
export const tenderDocumentCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    qa: "Fragen und Antworten",
    title: "Ausschreibungsunterlagen",
    files: "Gespeicherte Originale",
    set: "Gespeicherter Dokumentensatz",
    help: "Nur zulässige gespeicherte Belege werden angezeigt. Die Textextraktion erfasst keine Diagramme oder gescannten Inhalte. Die Originaldateien bleiben massgebend.",
    none: "Keine lesbaren gespeicherten Dokumente in dieser Auswahl. Dies belegt nicht, dass die Quelle keine Dokumente enthält.",
    open: "Gespeicherten Text lesen",
    download: "Originaldatei herunterladen",
    compare: "Gespeicherte Versionen vergleichen",
    before: "Vorher",
    after: "Nachher",
    page: "Seite",
    location: "Fundstelle",
    partial:
      "Die Textextraktion ist unvollständig. Prüfen Sie die Originaldatei auf fehlende Informationen.",
    failed:
      "Keine geprüfte Textextraktion verfügbar. Die Originaldatei lässt sich möglicherweise in einer geeigneten Anwendung lesen.",
    unchanged:
      "Nach Vereinheitlichung der Leerzeichen wurde kein Textunterschied gefunden. Die Dateibytes können dennoch abweichen.",
    truncated:
      "Dies ist ein begrenzter Auszug. Laden Sie beide Originale für die vollständigen Belege herunter.",
    unavailable:
      "Belege sind nicht verfügbar. Zugriff oder Aufbewahrung können sich geändert haben. Aktualisieren Sie die Ansicht.",
    literal:
      "Dies sind wörtliche Textunterschiede, keine Auslegung der Vergabeanforderungen.",
    withdrawn: "Zurückgezogen",
    removed: "Aus der Quellenliste entfernt",
    incompleteSet: "Die Quellenliste war unvollständig.",
  },
  "fr-CH": {
    qa: "Questions et réponses",
    title: "Documents de l’appel d’offres",
    files: "Originaux conservés",
    set: "Ensemble de documents enregistré",
    help: "Seules les preuves conservées et autorisées sont affichées. L’extraction de texte ne couvre pas les schémas ni les contenus numérisés. Les fichiers originaux font foi.",
    none: "Aucun document conservé lisible dans cette sélection. Cela ne prouve pas que la source ne contient aucun document.",
    open: "Lire le texte enregistré",
    download: "Télécharger le fichier original",
    compare: "Comparer les versions enregistrées",
    before: "Avant",
    after: "Après",
    page: "Page",
    location: "Emplacement dans la source",
    partial:
      "L’extraction de texte est incomplète. Consultez le fichier original pour les informations manquantes.",
    failed:
      "Aucune extraction de texte vérifiée n’est disponible. Le fichier original peut rester lisible dans une application adaptée.",
    unchanged:
      "Aucune différence textuelle après normalisation des espaces. Les octets du fichier peuvent néanmoins différer.",
    truncated:
      "Cet extrait est limité. Téléchargez les deux originaux pour consulter les preuves complètes.",
    unavailable:
      "Preuves indisponibles. L’accès ou la conservation ont peut-être changé. Actualisez pour vérifier.",
    literal:
      "Il s’agit de différences textuelles littérales, pas d’une interprétation des exigences du marché.",
    withdrawn: "Retiré",
    removed: "Supprimé de la liste de la source",
    incompleteSet: "La liste de la source était incomplète.",
  },
  "it-CH": {
    qa: "Domande e risposte",
    title: "Documenti del bando",
    files: "Originali conservati",
    set: "Insieme di documenti salvato",
    help: "Sono mostrate solo prove conservate e autorizzate. L’estrazione del testo non copre diagrammi o contenuti scansionati. I file originali fanno fede.",
    none: "Nessun documento conservato leggibile in questa selezione. Questo non dimostra che la fonte sia priva di documenti.",
    open: "Leggi il testo salvato",
    download: "Scarica il file originale",
    compare: "Confronta le versioni salvate",
    before: "Prima",
    after: "Dopo",
    page: "Pagina",
    location: "Posizione nella fonte",
    partial:
      "L’estrazione del testo è incompleta. Consulta il file originale per le informazioni mancanti.",
    failed:
      "Non è disponibile un’estrazione di testo verificata. Il file originale potrebbe essere leggibile in un’applicazione adatta.",
    unchanged:
      "Nessuna differenza testuale dopo la normalizzazione degli spazi. I byte del file possono comunque differire.",
    truncated:
      "Questo estratto è limitato. Scarica entrambi gli originali per consultare le prove complete.",
    unavailable:
      "Prove non disponibili. L’accesso o la conservazione potrebbero essere cambiati. Aggiorna per verificare.",
    literal:
      "Queste sono differenze letterali del testo, non un’interpretazione dei requisiti di gara.",
    withdrawn: "Ritirato",
    removed: "Rimosso dall’elenco della fonte",
    incompleteSet: "L’elenco della fonte era incompleto.",
  },
  "rm-CH": {
    qa: "Dumondas e respostas",
    title: "Documents da la publicaziun",
    files: "Originals conservads",
    set: "Gruppa da documents memorisada",
    help: "Mo cumprovas conservadas ed autorisadas vegnan mussadas. L’extracziun dal text na cumpiglia betg diagrams u cuntegns scannads. Las datotecas originalas restan decisivas.",
    none: "Nagins documents conservads legibels en questa selecziun. Quai na cumprova betg che la funtauna na cuntegna nagins documents.",
    open: "Leger il text memorisà",
    download: "Telechargiar il document original",
    compare: "Cumparegliar versiuns memorisadas",
    before: "Avant",
    after: "Suenter",
    page: "Pagina",
    location: "Lieu en la funtauna",
    partial:
      "L’extracziun dal text è incumpletta. Consultai il document original per las infurmaziuns mancantas.",
    failed:
      "Naginas extracziuns dal text verifitgadas disponiblas. Il document original po esser legibel cun in’applicaziun adattada.",
    unchanged:
      "Naginas differenzas dal text suenter normalisar ils spazis. Ils bytes dal document pon tuttina differir.",
    truncated:
      "Quest extract è limità. Telechargiai omadus originals per las cumprovas cumplettas.",
    unavailable:
      "Cumprovas betg disponiblas. L’access u la conservaziun pon esser midads. Actualisai per controllar.",
    literal:
      "Quai èn differenzas litteralas dal text, betg in’interpretaziun da las pretensiuns da l’acquisiziun.",
    withdrawn: "Retratg",
    removed: "Allontanà da la glista da la funtauna",
    incompleteSet: "La glista da la funtauna era incumpletta.",
  },
};
