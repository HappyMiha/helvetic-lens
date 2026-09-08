import type { Locale } from "./i18n";
import type { Passage } from "./types";

export type NativeSnapshot = {
  id: string;
  version_key: string;
  saved_at: string;
  evidence_url: string;
};
export type NativeBaselineCandidates = {
  items: NativeSnapshot[];
  next_after: string | null;
  after_version_id: string;
};
export type NativeComparisonPage = {
  event_id: string;
  title: string;
  language: string;
  after: NativeSnapshot;
  before: NativeSnapshot | null;
  revision: number;
  status: "ready" | "unselected" | "stale";
  comparison_id: string | null;
  counts: Record<string, number> | null;
  material_count: number | null;
  items: {
    id: string;
    kind: string;
    classification: string;
    old: Passage | null;
    new: Passage | null;
  }[];
  pagination: {
    offset: number;
    total: number;
    next_offset: number | null;
    previous_offset: number | null;
  } | null;
};
type Copy = {
  title: string;
  help: string;
  before: string;
  after: string;
  choose: string;
  save: string;
  clear: string;
  saving: string;
  saved: string;
  cleared: string;
  empty: string;
  more: string;
  unselected: string;
  stale: string;
  readOnly: string;
  material: string;
  all: string;
  unchanged: string;
  noChanges: string;
  none: string;
  notice: string;
  savedAt: string;
  error: string;
};
export const nativeBaselineCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Compare saved versions",
    help: "Choose the saved version to compare against this event. Your organization shares this choice. Comparison direction does not establish which version was legally in force.",
    before: "Baseline version",
    after: "Event version",
    choose: "Choose a saved baseline",
    save: "Save and compare",
    clear: "Clear baseline",
    saving: "Saving the complete comparison…",
    saved: "Baseline saved. The comparison is ready to inspect.",
    cleared: "Baseline cleared.",
    empty:
      "No other accessible saved version is available on this page. Only versions of the same work and language can be compared.",
    more: "More saved versions",
    unselected:
      "Choose a baseline to see changes. We will not guess a previous version from its download date.",
    stale:
      "The selected comparison needs review: its evidence or access changed. Choose an available baseline and save again, or clear the choice.",
    readOnly:
      "You can inspect the comparison. Ask a workspace administrator to change its baseline.",
    material: "Material changes",
    all: "All passages",
    unchanged: "Unchanged",
    noChanges:
      "No material changes were identified by the deterministic comparison. This is not a legal impact assessment.",
    none: "No passage on this side",
    notice:
      "Exact saved text. This operation does not run AI or change legal dates. Open the evidence to check the source.",
    savedAt: "Saved",
    error:
      "Could not save the baseline. Your selection was not confirmed; reload the comparison before trying again.",
  },
  "de-CH": {
    title: "Gespeicherte Versionen vergleichen",
    help: "Wählen Sie die Vergleichsversion für dieses Ereignis. Ihre Organisation teilt diese Auswahl. Die Vergleichsrichtung belegt nicht, welche Fassung rechtlich galt.",
    before: "Basisversion",
    after: "Ereignisversion",
    choose: "Gespeicherte Basis wählen",
    save: "Speichern und vergleichen",
    clear: "Basis aufheben",
    saving: "Vollständiger Vergleich wird gespeichert…",
    saved: "Basis gespeichert. Der Vergleich kann geprüft werden.",
    cleared: "Basis aufgehoben.",
    empty:
      "Auf dieser Seite ist keine weitere zugängliche Version verfügbar. Nur Fassungen desselben Werks und derselben Sprache sind vergleichbar.",
    more: "Weitere gespeicherte Versionen",
    unselected:
      "Wählen Sie eine Basis, um Änderungen zu sehen. Das Herunterladedatum bestimmt keine Vorgängerversion.",
    stale:
      "Der gewählte Vergleich muss geprüft werden: Belege oder Zugriffsrechte haben sich geändert. Wählen und speichern Sie eine verfügbare Basis oder heben Sie die Auswahl auf.",
    readOnly:
      "Sie können den Vergleich prüfen. Eine Workspace-Administration kann die Basis ändern.",
    material: "Inhaltliche Änderungen",
    all: "Alle Passagen",
    unchanged: "Unverändert",
    noChanges:
      "Der deterministische Vergleich hat keine inhaltlichen Änderungen erkannt. Dies ist keine rechtliche Folgenabschätzung.",
    none: "Keine Passage auf dieser Seite",
    notice:
      "Exakter gespeicherter Text. Dieser Vorgang startet keine KI und ändert keine Rechtsdaten. Prüfen Sie die Quelle im Beleg.",
    savedAt: "Gespeichert",
    error:
      "Die Basis konnte nicht gespeichert werden. Laden Sie den Vergleich vor einem erneuten Versuch neu.",
  },
  "fr-CH": {
    title: "Comparer les versions enregistrées",
    help: "Choisissez la version de référence pour cet événement. Ce choix est partagé par votre organisation. Le sens de comparaison ne prouve pas quelle version était juridiquement en vigueur.",
    before: "Version de référence",
    after: "Version de l’événement",
    choose: "Choisir une référence enregistrée",
    save: "Enregistrer et comparer",
    clear: "Retirer la référence",
    saving: "Enregistrement de la comparaison complète…",
    saved: "Référence enregistrée. La comparaison peut être examinée.",
    cleared: "Référence retirée.",
    empty:
      "Aucune autre version accessible sur cette page. Seules les versions du même texte et de la même langue peuvent être comparées.",
    more: "Autres versions enregistrées",
    unselected:
      "Choisissez une référence pour voir les changements. La date de téléchargement ne détermine pas une version précédente.",
    stale:
      "La comparaison doit être réexaminée : les preuves ou les accès ont changé. Choisissez et enregistrez une référence disponible, ou retirez ce choix.",
    readOnly:
      "Vous pouvez consulter la comparaison. Un administrateur de l’espace peut modifier la référence.",
    material: "Changements de fond",
    all: "Tous les passages",
    unchanged: "Inchangé",
    noChanges:
      "La comparaison déterministe n’a identifié aucun changement de fond. Ce n’est pas une évaluation des effets juridiques.",
    none: "Aucun passage de ce côté",
    notice:
      "Texte enregistré exact. Cette opération ne lance pas l’IA et ne modifie aucune date juridique. Ouvrez la preuve pour vérifier la source.",
    savedAt: "Enregistré",
    error:
      "Impossible d’enregistrer la référence. Rechargez la comparaison avant de réessayer.",
  },
  "it-CH": {
    title: "Confronta le versioni salvate",
    help: "Scegli la versione di riferimento per questo evento. La scelta è condivisa nella tua organizzazione. La direzione del confronto non dimostra quale versione fosse legalmente in vigore.",
    before: "Versione di riferimento",
    after: "Versione dell’evento",
    choose: "Scegli un riferimento salvato",
    save: "Salva e confronta",
    clear: "Rimuovi riferimento",
    saving: "Salvataggio del confronto completo…",
    saved: "Riferimento salvato. Il confronto è pronto per la verifica.",
    cleared: "Riferimento rimosso.",
    empty:
      "Nessun’altra versione accessibile in questa pagina. Si possono confrontare solo versioni dello stesso testo e della stessa lingua.",
    more: "Altre versioni salvate",
    unselected:
      "Scegli un riferimento per vedere le modifiche. La data di download non determina una versione precedente.",
    stale:
      "Il confronto richiede una verifica: prove o accessi sono cambiati. Scegli e salva un riferimento disponibile oppure rimuovi la scelta.",
    readOnly:
      "Puoi consultare il confronto. Un amministratore dello spazio può cambiare il riferimento.",
    material: "Modifiche sostanziali",
    all: "Tutti i passaggi",
    unchanged: "Invariato",
    noChanges:
      "Il confronto deterministico non ha rilevato modifiche sostanziali. Non è una valutazione degli effetti giuridici.",
    none: "Nessun passaggio da questo lato",
    notice:
      "Testo salvato esatto. Questa operazione non avvia l’IA e non modifica date giuridiche. Apri la prova per verificare la fonte.",
    savedAt: "Salvato",
    error:
      "Impossibile salvare il riferimento. Ricarica il confronto prima di riprovare.",
  },
  "rm-CH": {
    title: "Cumparegliar versiuns memorisadas",
    help: "Tscherna la versiun da referenza per quest eveniment. L’organisaziun parta questa tscherna. La direcziun da cumparegliaziun na cumprova betg tge versiun ch’era legalmain en vigur.",
    before: "Versiun da referenza",
    after: "Versiun da l’eveniment",
    choose: "Tscherner ina referenza memorisada",
    save: "Memorisar e cumparegliar",
    clear: "Allontanar la referenza",
    saving: "Memorisar la cumparegliaziun cumpletta…",
    saved: "Referenza memorisada. La cumparegliaziun po vegnir examinada.",
    cleared: "Referenza allontanada.",
    empty:
      "Naginas autras versiuns accessiblas sin questa pagina. Mo versiuns dal medem text e da la medema lingua pon vegnir cumparegliadas.",
    more: "Ulteriuras versiuns memorisadas",
    unselected:
      "Tscherna ina referenza per vesair las midadas. La data da chargiada na determinescha betg ina versiun precedenta.",
    stale:
      "La cumparegliaziun sto vegnir examinada: cumprovas u access èn sa midads. Tscherna e memorisescha ina referenza disponibla u allontanescha la tscherna.",
    readOnly:
      "Ti pos consultar la cumparegliaziun. In administratur dal spazi po midar la referenza.",
    material: "Midadas dal ccuntegn",
    all: "Tut ils passadis",
    unchanged: "Nunmidà",
    noChanges:
      "La cumparegliaziun deterministica n’ha identifitgà naginas midadas dal ccuntegn. Quai n’è betg ina valitaziun da las consequenzas giuridicas.",
    none: "Nagin passadi da questa vart",
    notice:
      "Text memorisà exact. Questa operaziun na lantscha nagina IA e na mida naginas datas giuridicas. Avra la cumprova per controllar la funtauna.",
    savedAt: "Memorisà",
    error:
      "La referenza n’ha betg pudì vegnir memorisada. Chargia danovamain la cumparegliaziun avant d’empruvar anc ina giada.",
  },
};
