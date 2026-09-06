import type { Locale } from "./i18n";

type Copy = {
  title: string;
  body: string;
  scope: string;
  rule: string;
  batch: string;
  preview: string;
  apply: string;
  confirmTitle: string;
  confirmBody: string;
  acknowledge: string;
  confirm: string;
  back: string;
  recent: string;
  recentHelp: string;
  empty: string;
  previewMode: string;
  applyMode: string;
  unknownMode: string;
  progress: string;
  changed: string;
  retained: string;
  rejected: string;
  skipped: string;
  removed: string;
  examples: string;
  examplesHelp: string;
  reasons: string;
  score: string;
  noChanges: string;
  superseded: string;
  obsolete: string;
  unavailable: string;
  captured: string;
  noResult: string;
  resume: string;
  unknownRequest: string;
  retryRequest: string;
  storageError: string;
  source: string;
  target: string;
  complete: string;
  partial: string;
  preserved: string;
};

export const reprocessingCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Recheck saved leads",
    body: "Preview how today's matching rules treat existing links between documents. Apply only after reviewing the results.",
    scope:
      "Platform-wide candidate metadata. No new document pairs, AI requests or notifications. Saved conclusions and human reviews stay in history.",
    rule: "Current rule",
    batch: "Candidates per batch",
    preview: "Preview changes",
    apply: "Review and apply",
    confirmTitle: "Apply a fresh recheck?",
    confirmBody:
      "This uses the latest saved metadata, so it can differ from the preview. Changed candidates make older AI conclusions stale. Earlier completed batches are kept if you cancel.",
    acknowledge:
      "I understand the platform-wide scope and want to apply the recheck.",
    confirm: "Apply recheck",
    back: "Back to platform admin",
    recent: "Recent runs",
    recentHelp:
      "Latest 20 runs started in this organization. Select one to inspect or resume it.",
    empty: "No runs yet. Start with a preview; it does not change candidates.",
    previewMode: "Preview only",
    applyMode: "Apply changes",
    unknownMode: "Mode unavailable",
    progress: "Candidates checked",
    changed: "Changed",
    retained: "Still supported",
    rejected: "No longer supported",
    skipped: "Skipped",
    removed: "Deleted since capture",
    examples: "Changed examples",
    examplesHelp:
      "Up to 10 saved examples, not the entire result. Rejection means insufficient retrieval support, not a legal no-impact conclusion.",
    reasons: "Saved rule explanation",
    score: "Retrieval score",
    noChanges:
      "No candidate changes found. Current usable AI conclusions stay available without another model request.",
    superseded:
      "The rule changed during this run. Completed batches remain saved; start a new preview for the current rule.",
    obsolete:
      "This preview used an earlier rule. Start a new preview before applying.",
    unavailable:
      "The result is unavailable or incomplete. Refresh to recover the saved job; do not start another apply to guess its outcome.",
    captured: "Admission cutoff",
    noResult:
      "The first batch has not returned yet. You can leave this page; the job continues in the background.",
    resume: "Resume saved run",
    unknownRequest:
      "A request has not been acknowledged. Retry the same saved request to recover its job without creating a duplicate.",
    retryRequest: "Recover submitted request",
    storageError:
      "The browser could not save the request identity. Allow session storage before starting maintenance.",
    source: "Source document",
    target: "Monitored document",
    complete: "Recheck complete",
    partial: "Completed batches only",
    preserved: "History preserved · no AI or notification calls",
  },
  "de-CH": {
    title: "Gespeicherte Hinweise erneut prüfen",
    body: "Prüfen Sie vorab, wie die heutigen Abgleichregeln bestehende Dokumentverknüpfungen bewerten. Übernehmen Sie Änderungen erst nach der Prüfung.",
    scope:
      "Kandidatenmetadaten der gesamten Plattform. Keine neuen Dokumentpaare, KI-Anfragen oder Benachrichtigungen. Gespeicherte Einschätzungen und menschliche Prüfungen bleiben im Verlauf.",
    rule: "Aktuelle Regel",
    batch: "Kandidaten pro Durchlauf",
    preview: "Änderungen vorprüfen",
    apply: "Prüfen und übernehmen",
    confirmTitle: "Neue Prüfung anwenden?",
    confirmBody:
      "Dabei werden die neuesten gespeicherten Metadaten verwendet. Das Ergebnis kann von der Vorschau abweichen. Geänderte Kandidaten machen frühere KI-Einschätzungen veraltet. Bereits abgeschlossene Durchläufe bleiben bei einem Abbruch erhalten.",
    acknowledge:
      "Ich verstehe den plattformweiten Umfang und möchte die Prüfung anwenden.",
    confirm: "Prüfung anwenden",
    back: "Zur Plattformverwaltung",
    recent: "Letzte Prüfungen",
    recentHelp:
      "Die letzten 20 in dieser Organisation gestarteten Prüfungen. Wählen Sie eine zum Prüfen oder Fortsetzen aus.",
    empty:
      "Noch keine Prüfung. Beginnen Sie mit einer Vorschau; sie ändert keine Kandidaten.",
    previewMode: "Nur Vorschau",
    applyMode: "Änderungen anwenden",
    unknownMode: "Modus nicht verfügbar",
    progress: "Geprüfte Kandidaten",
    changed: "Geändert",
    retained: "Weiterhin gestützt",
    rejected: "Nicht mehr gestützt",
    skipped: "Übersprungen",
    removed: "Seit Erfassung gelöscht",
    examples: "Geänderte Beispiele",
    examplesHelp:
      "Bis zu 10 gespeicherte Beispiele, nicht das ganze Ergebnis. Eine Ablehnung bedeutet fehlende Grundlage für den Abgleich, keine rechtliche Aussage über fehlende Auswirkungen.",
    reasons: "Gespeicherte Regelbegründung",
    score: "Abgleichwert",
    noChanges:
      "Keine Kandidatenänderungen gefunden. Aktuelle nutzbare KI-Einschätzungen bleiben ohne neue Modellanfrage verfügbar.",
    superseded:
      "Die Regel wurde während der Prüfung geändert. Abgeschlossene Durchläufe bleiben gespeichert. Starten Sie eine neue Vorschau mit der aktuellen Regel.",
    obsolete:
      "Diese Vorschau verwendet eine frühere Regel. Starten Sie vor dem Anwenden eine neue Vorschau.",
    unavailable:
      "Das Ergebnis fehlt oder ist unvollständig. Laden Sie den gespeicherten Auftrag erneut. Starten Sie keine weitere Anwendung, um das Ergebnis zu erraten.",
    captured: "Erfassungsgrenze",
    noResult:
      "Der erste Durchlauf ist noch nicht zurückgekehrt. Sie können die Seite verlassen; der Auftrag läuft im Hintergrund weiter.",
    resume: "Gespeicherte Prüfung fortsetzen",
    unknownRequest:
      "Eine Anfrage wurde noch nicht bestätigt. Wiederholen Sie dieselbe gespeicherte Anfrage, um den Auftrag ohne Duplikat wiederzufinden.",
    retryRequest: "Gesendete Anfrage wiederfinden",
    storageError:
      "Der Browser konnte die Anfragekennung nicht speichern. Erlauben Sie Sitzungsspeicher, bevor Sie die Wartung starten.",
    source: "Quelldokument",
    target: "Überwachtes Dokument",
    complete: "Prüfung abgeschlossen",
    partial: "Nur abgeschlossene Durchläufe",
    preserved: "Verlauf erhalten · keine KI- oder Benachrichtigungsaufrufe",
  },
  "fr-CH": {
    title: "Réexaminer les pistes enregistrées",
    body: "Prévisualisez l'effet des règles actuelles sur les liens existants entre documents. Appliquez les changements après examen.",
    scope:
      "Métadonnées des candidats de toute la plateforme. Aucune nouvelle paire, requête IA ou notification. Les conclusions et les examens humains restent dans l'historique.",
    rule: "Règle actuelle",
    batch: "Candidats par lot",
    preview: "Prévisualiser",
    apply: "Examiner et appliquer",
    confirmTitle: "Appliquer un nouvel examen ?",
    confirmBody:
      "Les dernières métadonnées enregistrées seront utilisées ; le résultat peut différer de l'aperçu. Les candidats modifiés rendent les anciennes conclusions IA obsolètes. Les lots terminés restent enregistrés en cas d'annulation.",
    acknowledge:
      "Je comprends la portée sur toute la plateforme et souhaite appliquer l'examen.",
    confirm: "Appliquer l'examen",
    back: "Administration de la plateforme",
    recent: "Examens récents",
    recentHelp:
      "Les 20 derniers examens lancés dans cette organisation. Sélectionnez-en un pour le consulter ou le reprendre.",
    empty:
      "Aucun examen. Commencez par un aperçu ; il ne modifie pas les candidats.",
    previewMode: "Aperçu uniquement",
    applyMode: "Application",
    unknownMode: "Mode indisponible",
    progress: "Candidats examinés",
    changed: "Modifiés",
    retained: "Toujours étayés",
    rejected: "Plus étayés",
    skipped: "Ignorés",
    removed: "Supprimés depuis la capture",
    examples: "Exemples modifiés",
    examplesHelp:
      "Jusqu'à 10 exemples enregistrés, pas le résultat complet. Le rejet indique un rapprochement insuffisamment étayé, pas une conclusion juridique d'absence d'impact.",
    reasons: "Justification enregistrée",
    score: "Score de rapprochement",
    noChanges:
      "Aucun changement de candidat. Les conclusions IA actuelles restent disponibles sans nouvelle requête au modèle.",
    superseded:
      "La règle a changé pendant cet examen. Les lots terminés restent enregistrés ; lancez un nouvel aperçu avec la règle actuelle.",
    obsolete:
      "Cet aperçu utilise une ancienne règle. Lancez un nouvel aperçu avant d'appliquer.",
    unavailable:
      "Le résultat est absent ou incomplet. Actualisez pour retrouver le travail enregistré ; ne lancez pas une nouvelle application pour deviner son résultat.",
    captured: "Limite d'admission",
    noResult:
      "Le premier lot n'est pas encore revenu. Vous pouvez quitter la page ; le travail continue en arrière-plan.",
    resume: "Reprendre l'examen",
    unknownRequest:
      "Une requête n'a pas été confirmée. Réessayez la même requête enregistrée pour retrouver le travail sans doublon.",
    retryRequest: "Retrouver la requête envoyée",
    storageError:
      "Le navigateur n'a pas pu enregistrer l'identifiant. Autorisez le stockage de session avant de lancer la maintenance.",
    source: "Document source",
    target: "Document surveillé",
    complete: "Examen terminé",
    partial: "Lots terminés uniquement",
    preserved: "Historique préservé · aucun appel IA ni notification",
  },
  "it-CH": {
    title: "Ricontrolla le segnalazioni salvate",
    body: "Visualizza l'effetto delle regole attuali sui collegamenti esistenti tra documenti. Applica le modifiche solo dopo averle esaminate.",
    scope:
      "Metadati dei candidati di tutta la piattaforma. Nessuna nuova coppia, richiesta IA o notifica. Le conclusioni e le revisioni umane restano nella cronologia.",
    rule: "Regola attuale",
    batch: "Candidati per lotto",
    preview: "Anteprima modifiche",
    apply: "Esamina e applica",
    confirmTitle: "Applicare un nuovo controllo?",
    confirmBody:
      "Verranno usati gli ultimi metadati salvati: il risultato può differire dall'anteprima. I candidati modificati rendono obsolete le precedenti conclusioni IA. I lotti completati restano salvati anche se annulli.",
    acknowledge:
      "Comprendo l'ambito dell'intera piattaforma e desidero applicare il controllo.",
    confirm: "Applica il controllo",
    back: "Amministrazione piattaforma",
    recent: "Controlli recenti",
    recentHelp:
      "Gli ultimi 20 controlli avviati in questa organizzazione. Selezionane uno per esaminarlo o riprenderlo.",
    empty:
      "Nessun controllo. Inizia da un'anteprima: non modifica i candidati.",
    previewMode: "Solo anteprima",
    applyMode: "Applicazione",
    unknownMode: "Modalità non disponibile",
    progress: "Candidati controllati",
    changed: "Modificati",
    retained: "Ancora supportati",
    rejected: "Non più supportati",
    skipped: "Saltati",
    removed: "Eliminati dopo la cattura",
    examples: "Esempi modificati",
    examplesHelp:
      "Fino a 10 esempi salvati, non il risultato completo. Il rifiuto indica un collegamento non sufficientemente supportato, non una conclusione giuridica di assenza d'impatto.",
    reasons: "Motivazione salvata",
    score: "Punteggio di corrispondenza",
    noChanges:
      "Nessuna modifica ai candidati. Le conclusioni IA attuali restano disponibili senza una nuova richiesta al modello.",
    superseded:
      "La regola è cambiata durante il controllo. I lotti completati restano salvati; avvia una nuova anteprima con la regola attuale.",
    obsolete:
      "Questa anteprima usa una regola precedente. Avviane una nuova prima di applicare.",
    unavailable:
      "Il risultato non è disponibile o è incompleto. Aggiorna per recuperare il lavoro salvato; non avviare una nuova applicazione per indovinarne l'esito.",
    captured: "Limite di ammissione",
    noResult:
      "Il primo lotto non è ancora terminato. Puoi lasciare la pagina: il lavoro continua in background.",
    resume: "Riprendi il controllo",
    unknownRequest:
      "Una richiesta non è stata confermata. Ripeti la stessa richiesta salvata per recuperare il lavoro senza duplicati.",
    retryRequest: "Recupera richiesta inviata",
    storageError:
      "Il browser non ha potuto salvare l'identificativo. Consenti l'archiviazione di sessione prima della manutenzione.",
    source: "Documento fonte",
    target: "Documento monitorato",
    complete: "Controllo completato",
    partial: "Solo lotti completati",
    preserved: "Cronologia preservata · nessuna chiamata IA o notifica",
  },
  "rm-CH": {
    title: "Examinar danovamain ils indizis memorisads",
    body: "Vesair ordavant co las reglas actualas tractan las colliaziuns existentas tranter documents. Applitgar las midadas suenter l'examinaziun.",
    scope:
      "Metadatas dals candidats da l'entira plattafurma. Naginas novas pèras, dumondas IA u notificaziuns. Conclusiuns e controllas umanas restan en l'istorgia.",
    rule: "Regla actuala",
    batch: "Candidats per gruppa",
    preview: "Prevista da las midadas",
    apply: "Examinar ed applitgar",
    confirmTitle: "Applitgar ina nova examinaziun?",
    confirmBody:
      "Las ultimas metadatas memorisadas vegnan duvradas. Il resultat po differir da la prevista. Candidats midads rendan antiquadas las conclusiuns IA anteriuras. Gruppas terminadas restan memorisadas en cas d'interrupziun.",
    acknowledge:
      "Jau chapesch la dimensiun per l'entira plattafurma e vul applitgar l'examinaziun.",
    confirm: "Applitgar l'examinaziun",
    back: "Administraziun da la plattafurma",
    recent: "Examinaziuns recentas",
    recentHelp:
      "Las ultimas 20 examinaziuns iniziadas en questa organisaziun. Tscherner ina per examinar u cuntinuar.",
    empty:
      "Anc nagina examinaziun. Cumenzar cun ina prevista; ella na mida nagins candidats.",
    previewMode: "Mo prevista",
    applyMode: "Applitgar midadas",
    unknownMode: "Modus betg disponibel",
    progress: "Candidats examinads",
    changed: "Midads",
    retained: "Anc sustegnids",
    rejected: "Betg pli sustegnids",
    skipped: "Sursiglids",
    removed: "Stizzads suenter la registraziun",
    examples: "Exempels midads",
    examplesHelp:
      "Fin a 10 exempels memorisads, betg l'entir resultat. In refus signifitga in sustegn insuffizient per la colliaziun, betg ina conclusiun giuridica senza influenza.",
    reasons: "Motivaziun memorisada",
    score: "Valur da cumparegliaziun",
    noChanges:
      "Naginas midadas dals candidats. Las conclusiuns IA actualas restan disponiblas senza nova dumonda al model.",
    superseded:
      "La regla è vegnida midada durant questa examinaziun. Gruppas terminadas restan memorisadas; cumenzar ina nova prevista cun la regla actuala.",
    obsolete:
      "Questa prevista dovra ina regla anteriura. Cumenzar ina nova prevista avant d'applitgar.",
    unavailable:
      "Il resultat manca u n'è betg cumplet. Actualisar per chattar l'incumbensa memorisada; betg applitgar danovamain per sminar il resultat.",
    captured: "Limit da registraziun",
    noResult:
      "L'emprima gruppa n'è anc betg terminada. Vus pudais bandunar la pagina; l'incumbensa cuntinuescha en il fund.",
    resume: "Cuntinuar l'examinaziun",
    unknownRequest:
      "Ina dumonda n'è anc betg confermada. Repeter la medema dumonda memorisada per chattar l'incumbensa senza duplicat.",
    retryRequest: "Chattar la dumonda tramessa",
    storageError:
      "Il navigatur n'ha betg pudì memorisar l'identitad. Permetter la memoria da sessiun avant la mantegnientscha.",
    source: "Document da funtauna",
    target: "Document surveglià",
    complete: "Examinaziun terminada",
    partial: "Mo gruppas terminadas",
    preserved: "Istorgia mantegnida · naginas dumondas IA u notificaziuns",
  },
};
