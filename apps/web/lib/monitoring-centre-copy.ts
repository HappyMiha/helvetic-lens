import type { Locale } from "./i18n";

export const centreSources = {
  auctions: "Aste UEF · Ticino",
  ip: "IPI / IGE · Swissreg",
  commute: "opentransportdata.swiss",
  traffic: "FEDRO · opentransportdata.swiss",
  pollen: "MeteoSwiss",
  air: "Basel-Stadt · data.bs.ch",
  tenders: "SIMAP",
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
        "Choose places and warning types. Preview checks current official source access and geographic coverage before Start.",
      ],
      commute: [
        "Regular commute",
        "Configure a regular journey. Preview checks timetable matching and current official transport access before Start.",
      ],
      traffic: [
        "Road and tunnel traffic",
        "Choose roads and tunnels. Preview checks current FEDRO source access and coverage before Start.",
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
        "Public SIMAP tender discovery. Document and Q&A coverage remains unverified.",
      ],
      ip: [
        "IP Watch",
        "Configure a private trademark portfolio. Live register discovery still requires a supported source and permitted monitoring use.",
      ],
      auctions: [
        "Ticino auctions",
        "Configure asset interests and budgets. Preview checks current official source access before tracking lots.",
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
        "Orte und Warnarten wählen. Die Vorschau prüft vor dem Start den aktuellen offiziellen Quellenzugang und die geografische Abdeckung.",
      ],
      commute: [
        "Regelmässiger Arbeitsweg",
        "Einen regelmässigen Arbeitsweg konfigurieren. Die Vorschau prüft vor dem Start den Fahrplanabgleich und den aktuellen offiziellen Verkehrsdatenzugang.",
      ],
      traffic: [
        "Strassen und Tunnel",
        "Strassen und Tunnel wählen. Die Vorschau prüft vor dem Start den aktuellen ASTRA-Quellenzugang und die Abdeckung.",
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
        "Öffentliche SIMAP-Ausschreibungen finden. Dokumente und Fragen/Antworten bleiben unverifiziert.",
      ],
      ip: [
        "Geistiges Eigentum",
        "Ein privates Markenportfolio konfigurieren. Die Live-Registersuche erfordert weiterhin eine unterstützte Quelle und die erlaubte Nutzung zur Beobachtung.",
      ],
      auctions: [
        "Tessiner Auktionen",
        "Sachinteressen und Budgets konfigurieren. Die Vorschau prüft den aktuellen offiziellen Quellenzugang, bevor Lose verfolgt werden.",
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
        "Choisissez les lieux et types d’alertes. L’aperçu vérifie l’accès actuel à la source officielle et la couverture géographique avant le démarrage.",
      ],
      commute: [
        "Trajet régulier",
        "Configurez un trajet régulier. L’aperçu vérifie les correspondances horaires et l’accès actuel aux données officielles de transport avant le démarrage.",
      ],
      traffic: [
        "Routes et tunnels",
        "Choisissez les routes et tunnels. L’aperçu vérifie l’accès actuel aux sources OFROU et la couverture avant le démarrage.",
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
        "Recherche d’appels d’offres publics SIMAP. Documents et questions/réponses restent non vérifiés.",
      ],
      ip: [
        "Propriété intellectuelle",
        "Configurez un portefeuille privé de marques. La recherche en direct dans les registres exige encore une source prise en charge et un usage autorisé pour la veille.",
      ],
      auctions: [
        "Enchères tessinoises",
        "Configurez vos critères de biens et budgets. L’aperçu vérifie l’accès actuel à la source officielle avant le suivi des lots.",
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
        "Scegli luoghi e tipi di allerta. L’anteprima verifica l’accesso attuale alla fonte ufficiale e la copertura geografica prima dell’avvio.",
      ],
      commute: [
        "Tragitto regolare",
        "Configura un tragitto regolare. L’anteprima verifica la corrispondenza degli orari e l’accesso attuale ai dati ufficiali di trasporto prima dell’avvio.",
      ],
      traffic: [
        "Strade e gallerie",
        "Scegli strade e gallerie. L’anteprima verifica l’accesso attuale alle fonti USTRA e la copertura prima dell’avvio.",
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
        "Ricerca di appalti pubblici SIMAP. Documenti e domande/risposte restano non verificati.",
      ],
      ip: [
        "Proprietà intellettuale",
        "Configura un portafoglio privato di marchi. La ricerca dal vivo nei registri richiede ancora una fonte supportata e l’uso consentito per il monitoraggio.",
      ],
      auctions: [
        "Aste ticinesi",
        "Configura interessi per i beni e budget. L’anteprima verifica l’accesso attuale alla fonte ufficiale prima di seguire i lotti.",
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
        "Tscherni lieus e tips d’avertiment. La prevista verifitgescha l’access actual a la funtauna uffiziala e la cuvrida geografica avant il cumenzament.",
      ],
      commute: [
        "Viadi regular",
        "Configurai in viadi regular. La prevista verifitgescha la correspundenza cun l’urari e l’access actual a las datas uffizialas da transport avant il cumenzament.",
      ],
      traffic: [
        "Vias e tunnels",
        "Tscherni vias e tunnels. La prevista verifitgescha l’access actual a las funtaunas USTRA e la cuvrida avant il cumenzament.",
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
        "Tschertga da submissiuns publicas SIMAP. Documents e dumondas/respostas restan betg verifitgads.",
      ],
      ip: [
        "Proprietad intellectuala",
        "Configurai in portfolio privat da marcas. La tschertga directa en ils registers pretenda anc ina funtauna sustegnida e l’utilisaziun permessa per la surveglianza.",
      ],
      auctions: [
        "Inchants tessinais",
        "Configurai interess per bains e budgets. La prevista verifitgescha l’access actual a la funtauna uffiziala avant da suandar lots.",
      ],
    },
  },
};
