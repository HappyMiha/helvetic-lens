import type { Locale } from "./i18n";

export const centreSources = {
  pollen: "MeteoSwiss",
  air: "Basel-Stadt · data.bs.ch",
};
export const centreTimezone = "Europe/Zurich";

export type TemplateId =
  | "warnings"
  | "commute"
  | "traffic"
  | "pollen"
  | "river"
  | "air"
  | "tenders"
  | "ip"
  | "auctions";
type Copy = {
  title: string;
  intro: string;
  choose: string;
  personal: string;
  business: string;
  saved: string;
  all: string;
  domain: string;
  lifecycle: string;
  open: string;
  configure: string;
  available: string;
  blocked: string;
  disabled: string;
  preview_only: string;
  disabledHelp: string;
  previewHelp: string;
  empty: string;
  lastCheck: string;
  nextCheck: string;
  observation: string;
  none: string;
  legacy: string;
  topics: string;
  documents: string;
  legacyHelp: string;
  source: string;
  unknown: string;
  not_started: string;
  source_not_approved: string;
  source_unavailable: string;
  unavailable: string;
  scheduleHelp: string;
  templates: Record<TemplateId, [string, string]>;
};

export const centreCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Monitoring centre",
    intro:
      "Your private monitors in this workspace. Open a monitor to review thresholds, history, pause, resume or archive it.",
    choose: "Choose what to monitor",
    personal: "Personal",
    business: "Business",
    saved: "Your saved monitors",
    all: "All",
    domain: "Scenario",
    lifecycle: "Monitor status",
    open: "Open settings and history",
    configure: "Choose settings",
    available: "Available to configure",
    blocked: "Not available yet",
    disabled: "Disabled",
    preview_only: "Draft preview only",
    disabledHelp:
      "This scenario is disabled for this workspace. Saved settings are retained; contact the workspace administrator.",
    previewHelp:
      "Drafts can be previewed. Live activation is not enabled for this workspace.",
    empty:
      "No monitors match these filters. Choose a scenario or change the filters.",
    lastCheck: "Last check attempt",
    nextCheck: "Scheduled next check",
    observation: "Latest usable observation",
    none: "Not recorded",
    legacy: "Existing monitoring",
    topics: "Topics",
    documents: "Watched documents",
    legacyHelp:
      "Continue managing existing topics and legal documents in their original sections.",
    source: "Source",
    unknown: "Unknown",
    not_started: "Not started",
    source_not_approved: "Source approval required",
    source_unavailable: "Source unavailable",
    unavailable: "Current data unavailable",
    scheduleHelp:
      "Check times describe the schedule, not a successful observation. An overdue check may still be queued.",
    templates: {
      warnings: [
        "Local warnings",
        "The official warning feed and permitted automated use still need verification.",
      ],
      commute: [
        "Regular commute",
        "Official live transport access and timetable matching are not ready. No live journey alerts yet.",
      ],
      traffic: [
        "Road and tunnel traffic",
        "FEDRO access and permitted traffic coverage are not yet verified.",
      ],
      pollen: [
        "Pollen Watch",
        "Supported Swiss stations and allergens. Preview checks the exact observation and forecast coverage before Start.",
      ],
      river: [
        "River / Lake Watch",
        "Official Swiss station readings and published danger levels. Preview verifies the selected measurements.",
      ],
      air: [
        "Air Quality Watch",
        "Basel-Binningen: ozone, NO₂, PM10 and PM2.5. Other regions are not enabled.",
      ],
      tenders: [
        "Tender Watch",
        "SIMAP integration and publication/document access terms still need verification.",
      ],
      ip: [
        "IP Watch",
        "Register access and permitted monitoring use still need verification.",
      ],
      auctions: [
        "Ticino auctions",
        "A supported official channel and permitted automated monitoring still need verification.",
      ],
    },
  },
  "de-CH": {
    title: "Beobachtungszentrale",
    intro:
      "Ihre privaten Beobachtungen in diesem Arbeitsbereich. Öffnen Sie eine Beobachtung für Schwellenwerte, Verlauf, Pause, Fortsetzung oder Archivierung.",
    choose: "Was möchten Sie beobachten?",
    personal: "Privat",
    business: "Geschäftlich",
    saved: "Ihre gespeicherten Beobachtungen",
    all: "Alle",
    domain: "Szenario",
    lifecycle: "Beobachtungsstatus",
    open: "Einstellungen und Verlauf öffnen",
    configure: "Einstellungen wählen",
    available: "Konfiguration verfügbar",
    blocked: "Noch nicht verfügbar",
    disabled: "Deaktiviert",
    preview_only: "Nur Entwurfsvorschau",
    disabledHelp:
      "Dieses Szenario ist für den Arbeitsbereich deaktiviert. Einstellungen bleiben gespeichert. Wenden Sie sich an die Administration.",
    previewHelp:
      "Entwürfe können geprüft werden. Die Live-Aktivierung ist für diesen Arbeitsbereich nicht freigegeben.",
    empty:
      "Keine Beobachtungen mit diesen Filtern. Wählen Sie ein Szenario oder ändern Sie die Filter.",
    lastCheck: "Letzter Prüfversuch",
    nextCheck: "Nächste geplante Prüfung",
    observation: "Neueste nutzbare Beobachtung",
    none: "Nicht erfasst",
    legacy: "Bestehende Beobachtungen",
    topics: "Themen",
    documents: "Beobachtete Dokumente",
    legacyHelp:
      "Verwalten Sie bestehende Themen und Rechtsdokumente weiterhin in ihren ursprünglichen Bereichen.",
    source: "Quelle",
    unknown: "Unbekannt",
    not_started: "Nicht gestartet",
    source_not_approved: "Quellenfreigabe erforderlich",
    source_unavailable: "Quelle nicht verfügbar",
    unavailable: "Aktuelle Daten nicht verfügbar",
    scheduleHelp:
      "Prüfzeiten zeigen den Zeitplan, keinen erfolgreichen Datenabruf. Überfällige Prüfungen können noch in der Warteschlange sein.",
    templates: {
      warnings: [
        "Lokale Warnungen",
        "Der offizielle Warnkanal und die erlaubte automatisierte Nutzung müssen noch geprüft werden.",
      ],
      commute: [
        "Regelmässiger Arbeitsweg",
        "Offizieller Echtzeitzugang und Fahrplanabgleich sind noch nicht bereit. Noch keine Live-Reisewarnungen.",
      ],
      traffic: [
        "Strassen und Tunnel",
        "ASTRA-Zugang und erlaubte Verkehrsabdeckung sind noch nicht verifiziert.",
      ],
      pollen: [
        "Pollen Watch",
        "Unterstützte Schweizer Stationen und Allergene. Die Vorschau prüft vor dem Start die genaue Mess- und Prognoseabdeckung.",
      ],
      river: [
        "Fluss- / See-Beobachtung",
        "Offizielle Schweizer Stationsmessungen und veröffentlichte Gefahrenstufen. Die Vorschau prüft die gewählten Messgrössen.",
      ],
      air: [
        "Luftqualität",
        "Basel-Binningen: Ozon, NO₂, PM10 und PM2.5. Andere Regionen sind nicht freigeschaltet.",
      ],
      tenders: [
        "Ausschreibungen",
        "SIMAP-Anbindung und Zugangsbedingungen für Publikationen und Dokumente müssen noch geprüft werden.",
      ],
      ip: [
        "Geistiges Eigentum",
        "Registerzugang und erlaubte Nutzung zur Beobachtung müssen noch geprüft werden.",
      ],
      auctions: [
        "Tessiner Auktionen",
        "Ein unterstützter offizieller Kanal und die erlaubte automatisierte Beobachtung müssen noch geprüft werden.",
      ],
    },
  },
  "fr-CH": {
    title: "Centre de veille",
    intro:
      "Vos veilles privées dans cet espace. Ouvrez une veille pour consulter les seuils et l’historique, la suspendre, la reprendre ou l’archiver.",
    choose: "Que souhaitez-vous suivre ?",
    personal: "Personnel",
    business: "Entreprise",
    saved: "Vos veilles enregistrées",
    all: "Toutes",
    domain: "Scénario",
    lifecycle: "État de la veille",
    open: "Ouvrir les réglages et l’historique",
    configure: "Choisir les réglages",
    available: "Configuration disponible",
    blocked: "Pas encore disponible",
    disabled: "Désactivé",
    preview_only: "Aperçu du brouillon uniquement",
    disabledHelp:
      "Ce scénario est désactivé pour cet espace. Les réglages sont conservés ; contactez l’administration de l’espace.",
    previewHelp:
      "Les brouillons peuvent être prévisualisés. L’activation en direct n’est pas autorisée pour cet espace.",
    empty:
      "Aucune veille ne correspond aux filtres. Choisissez un scénario ou modifiez les filtres.",
    lastCheck: "Dernière tentative de vérification",
    nextCheck: "Prochaine vérification prévue",
    observation: "Dernière observation utilisable",
    none: "Non enregistré",
    legacy: "Veilles existantes",
    topics: "Thèmes",
    documents: "Documents suivis",
    legacyHelp:
      "Continuez à gérer les thèmes et documents juridiques existants dans leurs rubriques d’origine.",
    source: "Source",
    unknown: "Inconnu",
    not_started: "Non démarré",
    source_not_approved: "Approbation de la source requise",
    source_unavailable: "Source indisponible",
    unavailable: "Données actuelles indisponibles",
    scheduleHelp:
      "Les heures de vérification indiquent le calendrier, pas une observation réussie. Une vérification en retard peut encore être en attente.",
    templates: {
      warnings: [
        "Alertes locales",
        "Le flux officiel d’alertes et l’utilisation automatisée autorisée restent à vérifier.",
      ],
      commute: [
        "Trajet régulier",
        "L’accès officiel en direct et la correspondance avec les horaires ne sont pas prêts. Pas encore d’alertes de trajet en direct.",
      ],
      traffic: [
        "Routes et tunnels",
        "L’accès OFROU et la couverture de trafic autorisée ne sont pas encore vérifiés.",
      ],
      pollen: [
        "Pollen Watch",
        "Stations et allergènes suisses pris en charge. L’aperçu vérifie la couverture exacte des observations et prévisions avant le démarrage.",
      ],
      river: [
        "Rivières et lacs",
        "Mesures officielles des stations suisses et niveaux de danger publiés. L’aperçu vérifie les mesures sélectionnées.",
      ],
      air: [
        "Qualité de l’air",
        "Bâle-Binningen : ozone, NO₂, PM10 et PM2.5. Les autres régions ne sont pas activées.",
      ],
      tenders: [
        "Appels d’offres",
        "L’intégration SIMAP et les conditions d’accès aux publications et documents restent à vérifier.",
      ],
      ip: [
        "Propriété intellectuelle",
        "L’accès aux registres et l’utilisation autorisée pour la veille restent à vérifier.",
      ],
      auctions: [
        "Enchères tessinoises",
        "Un canal officiel pris en charge et la veille automatisée autorisée restent à vérifier.",
      ],
    },
  },
  "it-CH": {
    title: "Centro di monitoraggio",
    intro:
      "I tuoi monitoraggi privati in questo spazio. Apri un monitoraggio per soglie, cronologia, pausa, ripresa o archiviazione.",
    choose: "Che cosa vuoi monitorare?",
    personal: "Personale",
    business: "Aziendale",
    saved: "I tuoi monitoraggi salvati",
    all: "Tutti",
    domain: "Scenario",
    lifecycle: "Stato del monitoraggio",
    open: "Apri impostazioni e cronologia",
    configure: "Scegli impostazioni",
    available: "Configurazione disponibile",
    blocked: "Non ancora disponibile",
    disabled: "Disattivato",
    preview_only: "Solo anteprima della bozza",
    disabledHelp:
      "Questo scenario è disattivato per lo spazio. Le impostazioni sono conservate; contatta l’amministrazione dello spazio.",
    previewHelp:
      "È possibile visualizzare le bozze in anteprima. L’attivazione dal vivo non è abilitata per questo spazio.",
    empty:
      "Nessun monitoraggio corrisponde ai filtri. Scegli uno scenario o cambia i filtri.",
    lastCheck: "Ultimo tentativo di verifica",
    nextCheck: "Prossima verifica prevista",
    observation: "Ultima osservazione utilizzabile",
    none: "Non registrato",
    legacy: "Monitoraggi esistenti",
    topics: "Temi",
    documents: "Documenti monitorati",
    legacyHelp:
      "Continua a gestire i temi e i documenti giuridici esistenti nelle sezioni originali.",
    source: "Fonte",
    unknown: "Sconosciuto",
    not_started: "Non avviato",
    source_not_approved: "Approvazione della fonte necessaria",
    source_unavailable: "Fonte non disponibile",
    unavailable: "Dati attuali non disponibili",
    scheduleHelp:
      "Gli orari indicano la pianificazione, non un’osservazione riuscita. Una verifica in ritardo può essere ancora in coda.",
    templates: {
      warnings: [
        "Allerte locali",
        "Il canale ufficiale delle allerte e l’uso automatizzato consentito devono ancora essere verificati.",
      ],
      commute: [
        "Tragitto regolare",
        "Accesso ufficiale in tempo reale e corrispondenza degli orari non ancora pronti. Nessuna allerta di viaggio dal vivo.",
      ],
      traffic: [
        "Strade e gallerie",
        "L’accesso USTRA e la copertura del traffico consentita non sono ancora verificati.",
      ],
      pollen: [
        "Pollen Watch",
        "Stazioni e allergeni svizzeri supportati. L’anteprima verifica la copertura esatta di osservazioni e previsioni prima dell’avvio.",
      ],
      river: [
        "Fiumi e laghi",
        "Misure ufficiali delle stazioni svizzere e livelli di pericolo pubblicati. L’anteprima verifica le misure selezionate.",
      ],
      air: [
        "Qualità dell’aria",
        "Basilea-Binningen: ozono, NO₂, PM10 e PM2.5. Le altre regioni non sono abilitate.",
      ],
      tenders: [
        "Appalti",
        "Integrazione SIMAP e condizioni di accesso a pubblicazioni e documenti ancora da verificare.",
      ],
      ip: [
        "Proprietà intellettuale",
        "Accesso ai registri e uso consentito per il monitoraggio ancora da verificare.",
      ],
      auctions: [
        "Aste ticinesi",
        "Un canale ufficiale supportato e il monitoraggio automatizzato consentito devono ancora essere verificati.",
      ],
    },
  },
  "rm-CH": {
    title: "Center da surveglianza",
    intro:
      "Vossas surveglianzas privatas en quest spazi. Avri ina surveglianza per limitas, cronologia, pausa, cuntinuaziun u archivaziun.",
    choose: "Tge vulais Vus survegliar?",
    personal: "Privat",
    business: "Interpresa",
    saved: "Vossas surveglianzas memorisadas",
    all: "Tut",
    domain: "Scenari",
    lifecycle: "Status da surveglianza",
    open: "Avrir parameters e cronologia",
    configure: "Tscherner parameters",
    available: "Configuraziun disponibla",
    blocked: "Anc betg disponibel",
    disabled: "Deactivà",
    preview_only: "Mo prevista dal sboz",
    disabledHelp:
      "Quest scenari è deactivà per il spazi. Ils parameters restan memorisads; contactai l’administraziun dal spazi.",
    previewHelp:
      "Ins po examinar ils sbozs. L’activaziun directa n’è betg permessa per quest spazi.",
    empty:
      "Naginas surveglianzas correspundan als filters. Tscherni in scenari u midai ils filters.",
    lastCheck: "Ultima emprova da controlla",
    nextCheck: "Proxima controlla planisada",
    observation: "Ultima observaziun utilisabla",
    none: "Betg registrà",
    legacy: "Surveglianzas existentas",
    topics: "Temas",
    documents: "Documents survegliads",
    legacyHelp:
      "Administrai vinavant ils temas ed ils documents giuridics existents en lur rubricas originalas.",
    source: "Funtauna",
    unknown: "Nunenconuschent",
    not_started: "Betg cumenzà",
    source_not_approved: "Approvaziun da la funtauna necessaria",
    source_unavailable: "Funtauna betg disponibla",
    unavailable: "Datas actualas betg disponiblas",
    scheduleHelp:
      "Ils temps da controlla mussan il plan, betg in’observaziun reussida. Ina controlla retardada po anc esser en spetga.",
    templates: {
      warnings: [
        "Avertiments locals",
        "Il chanàl uffizial d’avertiments e l’utilisaziun automatisada permessa ston anc vegnir verifitgads.",
      ],
      commute: [
        "Viadi regular",
        "L’access uffizial en temp real e la cumparegliaziun cun l’urari n’èn anc betg pronts. Anc nagins avertiments da viadi directs.",
      ],
      traffic: [
        "Vias e tunnels",
        "L’access USTRA e la cuvrida dal traffic permessa n’èn anc betg verifitgads.",
      ],
      pollen: [
        "Pollen Watch",
        "Staziuns ed allergens svizzers sustegnids. La prevista verifitgescha la cuvrida exacta d’observaziuns e prognosas avant il cumenzament.",
      ],
      river: [
        "Flums e lais",
        "Mesiraziuns uffizialas da staziuns svizras e nivels da privel publitgads. La prevista verifitgescha las mesiras tschernidas.",
      ],
      air: [
        "Qualitad da l’aria",
        "Basilea-Binningen: ozon, NO₂, PM10 e PM2.5. Autras regiuns n’èn betg activadas.",
      ],
      tenders: [
        "Appaltaziuns",
        "L’integraziun SIMAP e las cundiziuns d’access a publicaziuns e documents ston anc vegnir verifitgadas.",
      ],
      ip: [
        "Proprietad intellectuala",
        "L’access als registers e l’utilisaziun permessa per la surveglianza ston anc vegnir verifitgads.",
      ],
      auctions: [
        "Inchants tessinais",
        "In chanàl uffizial sustegnì e la surveglianza automatisada permessa ston anc vegnir verifitgads.",
      ],
    },
  },
};
