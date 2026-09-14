import type { Locale } from "./i18n";
const en = {
  title: "Evidence packet for counsel review",
  prepare: "Prepare evidence packet",
  download: "Download HTML packet",
  preview: "Prepared evidence packet",
  include: "Include the selected register change and its previous evidence",
  currentOnly: "The packet includes current evidence only.",
  help: "Inspect the packet, then download it explicitly. No recipient is contacted and no filing or email is sent.",
  unavailable:
    "This packet cannot be exported: source rights, current evidence, access or preparation validity may have changed. Refresh the candidate and prepare again.",
  expires: "Preparation expires",
  static:
    "This is a static private export. It cannot update or redact itself after download. Verify current evidence and permitted use before sharing.",
  warning:
    "Candidate for IP review; no legal conflict or exhaustive clearance is confirmed. Verify the legal deadline before filing.",
  deadline: "Legal deadline",
  deadlineUnavailable:
    "No approved applicable rule is available. The legal deadline and days remaining are not calculated.",
  prepared: "Prepared",
  profile: "Portfolio revision",
  candidateVersion: "Candidate revision",
  decision: "Private decision",
  brand: "Monitored brand",
  provenance: "Evidence provenance",
  assessment: "Helvetic Lens assessment",
  previous: "Previous source evidence",
  selected: "Selected register change",
  current: "Current source evidence",
};
type Copy = { [K in keyof typeof en]: string };
export const trademarkExportCopy: Record<Locale, Copy> = {
  "en-CH": en,
  "de-CH": {
    title: "Belegpaket zur Rechtsberatung",
    prepare: "Belegpaket vorbereiten",
    download: "HTML-Paket herunterladen",
    preview: "Vorbereitetes Belegpaket",
    include: "Ausgewählte Registeränderung und vorherige Belege einschliessen",
    currentOnly: "Das Paket enthält nur aktuelle Belege.",
    help: "Prüfen Sie das Paket und laden Sie es ausdrücklich herunter. Niemand wird kontaktiert; keine Eingabe oder E-Mail wird gesendet.",
    unavailable:
      "Dieses Paket kann nicht exportiert werden: Quellenrechte, aktuelle Belege, Zugriff oder Gültigkeit können sich geändert haben. Aktualisieren Sie den Kandidaten und bereiten Sie es erneut vor.",
    expires: "Vorbereitung gültig bis",
    static:
      "Dies ist ein statischer privater Export. Nach dem Download kann er sich nicht aktualisieren oder Daten ausblenden. Prüfen Sie aktuelle Belege und zulässige Nutzung vor der Weitergabe.",
    warning:
      "Kandidat zur IP-Prüfung; kein Rechtskonflikt und keine vollständige Markenfreigabe bestätigt. Prüfen Sie die Rechtsfrist vor einer Eingabe.",
    deadline: "Rechtsfrist",
    deadlineUnavailable:
      "Keine genehmigte anwendbare Regel verfügbar. Rechtsfrist und verbleibende Tage werden nicht berechnet.",
    prepared: "Vorbereitet",
    profile: "Portfolioversion",
    candidateVersion: "Kandidatenversion",
    decision: "Private Entscheidung",
    brand: "Beobachtete Marke",
    provenance: "Belegherkunft",
    assessment: "Helvetic Lens Bewertung",
    previous: "Vorherige Quellenbelege",
    selected: "Ausgewählte Registeränderung",
    current: "Aktuelle Quellenbelege",
  },
  "fr-CH": {
    title: "Dossier de preuves pour conseil juridique",
    prepare: "Préparer le dossier",
    download: "Télécharger le dossier HTML",
    preview: "Dossier de preuves préparé",
    include: "Inclure le changement sélectionné et ses preuves précédentes",
    currentOnly: "Le dossier contient seulement les preuves actuelles.",
    help: "Examinez le dossier, puis téléchargez-le explicitement. Personne n’est contacté ; aucun dépôt ni e-mail n’est envoyé.",
    unavailable:
      "Ce dossier ne peut pas être exporté : les droits, preuves actuelles, accès ou validité peuvent avoir changé. Actualisez le candidat et préparez à nouveau.",
    expires: "Préparation valable jusqu’au",
    static:
      "Ceci est un export privé statique. Il ne peut plus s’actualiser ni masquer des données après téléchargement. Vérifiez les preuves actuelles et l’usage autorisé avant de le partager.",
    warning:
      "Candidat à un examen PI ; aucun conflit juridique ni disponibilité exhaustive n’est confirmé. Vérifiez le délai légal avant tout dépôt.",
    deadline: "Délai légal",
    deadlineUnavailable:
      "Aucune règle applicable approuvée n’est disponible. Le délai légal et les jours restants ne sont pas calculés.",
    prepared: "Préparé",
    profile: "Version du portefeuille",
    candidateVersion: "Version du candidat",
    decision: "Décision privée",
    brand: "Marque suivie",
    provenance: "Provenance des preuves",
    assessment: "Évaluation Helvetic Lens",
    previous: "Preuves sources précédentes",
    selected: "Changement sélectionné",
    current: "Preuves sources actuelles",
  },
  "it-CH": {
    title: "Dossier di prove per consulenza legale",
    prepare: "Prepara il dossier",
    download: "Scarica il dossier HTML",
    preview: "Dossier di prove preparato",
    include: "Includi la modifica selezionata e le prove precedenti",
    currentOnly: "Il dossier include solo le prove attuali.",
    help: "Esamina il dossier, poi scaricalo esplicitamente. Nessuno viene contattato; non vengono inviati depositi o email.",
    unavailable:
      "Questo dossier non può essere esportato: diritti, prove attuali, accesso o validità potrebbero essere cambiati. Aggiorna il candidato e prepara di nuovo.",
    expires: "Preparazione valida fino a",
    static:
      "Questo è un export privato statico. Non può aggiornarsi o oscurare dati dopo il download. Verifica le prove attuali e l’uso consentito prima di condividerlo.",
    warning:
      "Candidato alla revisione PI; nessun conflitto legale o disponibilità completa confermati. Verifica la scadenza legale prima di un deposito.",
    deadline: "Scadenza legale",
    deadlineUnavailable:
      "Nessuna regola applicabile approvata è disponibile. Scadenza legale e giorni restanti non vengono calcolati.",
    prepared: "Preparato",
    profile: "Versione del portafoglio",
    candidateVersion: "Versione del candidato",
    decision: "Decisione privata",
    brand: "Marchio monitorato",
    provenance: "Provenienza delle prove",
    assessment: "Valutazione Helvetic Lens",
    previous: "Prove precedenti della fonte",
    selected: "Modifica selezionata",
    current: "Prove attuali della fonte",
  },
  "rm-CH": {
    title: "Dossier da cumprovas per cussegl giuridic",
    prepare: "Preparar il dossier",
    download: "Telechargiar il dossier HTML",
    preview: "Dossier da cumprovas preparà",
    include: "Includer la midada tschernida e las cumprovas precedentas",
    currentOnly: "Il dossier cuntegna mo las cumprovas actualas.",
    help: "Controllai il dossier e telechargiai el explicitamain. Nagin vegn contactà; nagina inoltraziun u e-mail vegn tramessa.",
    unavailable:
      "Quest dossier na po betg vegnir exportà: dretgs, cumprovas actualas, access u valaivladad pon esser midads. Actualisai il candidat e preparai danovamain.",
    expires: "Preparaziun valaivla fin",
    static:
      "Quai è in export privat static. El na po betg s’actualisar u zuppar datas suenter la telechargia. Verifitgai las cumprovas actualas e l’utilisaziun permessa avant da parter el.",
    warning:
      "Candidat per controlla PI; nagin conflict giuridic u marca libra confermà. Verifitgai il termin giuridic avant in’inoltraziun.",
    deadline: "Termin giuridic",
    deadlineUnavailable:
      "Naginas reglas applitgablas approvadas èn disponiblas. Il termin giuridic ed ils dis restants na vegnan betg calculads.",
    prepared: "Preparà",
    profile: "Versiun dal portfolio",
    candidateVersion: "Versiun dal candidat",
    decision: "Decisiun privata",
    brand: "Marca observada",
    provenance: "Provenienza da las cumprovas",
    assessment: "Valitaziun Helvetic Lens",
    previous: "Cumprovas precedentas da la funtauna",
    selected: "Midada tschernida",
    current: "Cumprovas actualas da la funtauna",
  },
};
