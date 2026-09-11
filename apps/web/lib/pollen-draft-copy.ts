import type { Locale } from "./i18n";

type Copy = {
  title: string;
  note: string;
  station: string;
  settings: string;
  history: string;
  revision: string;
  loading: string;
  refresh: string;
  more: string;
  empty: string;
  select: string;
  disabled: string;
  access: string;
  missing: string;
  failed: string;
  start: string;
  blocked: string;
  threshold: string;
  reset: string;
  rapid: string;
  hours: string;
  category: string;
  noRules: string;
  delivery: string;
  quiet: string;
  timezone: string;
  unknown: string;
  allergens: Record<string, string>;
  periods: Record<string, string>;
  email: Record<string, string>;
};

export const pollenDraftCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Pollen Watch drafts",
    note: "Private saved settings. Station measurements do not describe the exact pollen level at your home. Live observations and forecasts are not available here.",
    station: "Station",
    settings: "Saved settings",
    history: "Configuration history",
    revision: "Revision",
    loading: "Loading…",
    refresh: "Reload drafts",
    more: "Load more",
    empty: "No saved drafts in this workspace.",
    select: "Select a draft to read its settings and history.",
    disabled: "Pollen Watch drafts are not enabled for this workspace.",
    access:
      "Sign in with an active workspace membership to read your private drafts.",
    missing: "This draft or page is no longer available. Reload the list.",
    failed: "Drafts could not be loaded. Try reloading.",
    start: "Start monitoring",
    blocked:
      "Starting is unavailable while official sources and the live workflow await verification. Saved email settings do not send any messages.",
    threshold: "Trigger at or above",
    reset: "Reset at or below",
    rapid: "Minimum increase",
    hours: "hours",
    category: "Category changes require a verified scale.",
    noRules: "No change rules saved.",
    delivery: "Saved email preference",
    quiet: "Quiet hours",
    timezone: "Time zone",
    unknown: "Unknown setting",
    allergens: {
      alder: "Alder",
      birch: "Birch",
      hazel: "Hazel",
      beech: "Beech",
      ash: "Ash",
      oak: "Oak",
      grasses: "Grasses",
      ragweed: "Ragweed",
    },
    periods: {
      observation_hourly: "Hourly observation",
      observation_daily_00_24_utc: "Daily mean, 00–24 UTC",
      observation_daily_06_06_utc: "Daily mean, 06–06 UTC",
      forecast_instant: "Forecast at a specific time",
    },
    email: { off: "Off", immediate: "Immediate", daily_digest: "Daily digest" },
  },
  "de-CH": {
    title: "Pollen-Watch-Entwürfe",
    note: "Privat gespeicherte Einstellungen. Stationsmessungen beschreiben nicht die genaue Pollenbelastung bei Ihnen zu Hause. Aktuelle Beobachtungen und Prognosen sind hier nicht verfügbar.",
    station: "Station",
    settings: "Gespeicherte Einstellungen",
    history: "Einstellungsverlauf",
    revision: "Version",
    loading: "Wird geladen…",
    refresh: "Entwürfe neu laden",
    more: "Mehr laden",
    empty: "Keine gespeicherten Entwürfe in diesem Arbeitsbereich.",
    select: "Wählen Sie einen Entwurf, um Einstellungen und Verlauf zu lesen.",
    disabled:
      "Pollen-Watch-Entwürfe sind für diesen Arbeitsbereich nicht freigeschaltet.",
    access:
      "Melden Sie sich mit einer aktiven Mitgliedschaft an, um Ihre privaten Entwürfe zu lesen.",
    missing:
      "Dieser Entwurf oder diese Seite ist nicht mehr verfügbar. Laden Sie die Liste neu.",
    failed: "Entwürfe konnten nicht geladen werden. Versuchen Sie es erneut.",
    start: "Überwachung starten",
    blocked:
      "Der Start ist bis zur Prüfung der offiziellen Quellen und des Live-Ablaufs nicht verfügbar. Gespeicherte E-Mail-Einstellungen versenden keine Nachrichten.",
    threshold: "Auslösen ab",
    reset: "Zurücksetzen bei höchstens",
    rapid: "Mindestanstieg",
    hours: "Stunden",
    category: "Kategorieänderungen benötigen eine geprüfte Skala.",
    noRules: "Keine Änderungsregeln gespeichert.",
    delivery: "Gespeicherte E-Mail-Präferenz",
    quiet: "Ruhezeiten",
    timezone: "Zeitzone",
    unknown: "Unbekannte Einstellung",
    allergens: {
      alder: "Erle",
      birch: "Birke",
      hazel: "Hasel",
      beech: "Buche",
      ash: "Esche",
      oak: "Eiche",
      grasses: "Gräser",
      ragweed: "Ambrosia",
    },
    periods: {
      observation_hourly: "Stündliche Beobachtung",
      observation_daily_00_24_utc: "Tagesmittel, 00–24 UTC",
      observation_daily_06_06_utc: "Tagesmittel, 06–06 UTC",
      forecast_instant: "Prognose für einen Zeitpunkt",
    },
    email: {
      off: "Aus",
      immediate: "Sofort",
      daily_digest: "Tägliche Zusammenfassung",
    },
  },
  "fr-CH": {
    title: "Brouillons Pollen Watch",
    note: "Paramètres enregistrés privés. Les mesures d’une station ne décrivent pas le niveau exact de pollen à votre domicile. Les observations et prévisions en direct ne sont pas disponibles ici.",
    station: "Station",
    settings: "Paramètres enregistrés",
    history: "Historique des paramètres",
    revision: "Révision",
    loading: "Chargement…",
    refresh: "Recharger les brouillons",
    more: "Charger la suite",
    empty: "Aucun brouillon enregistré dans cet espace.",
    select:
      "Sélectionnez un brouillon pour lire ses paramètres et son historique.",
    disabled:
      "Les brouillons Pollen Watch ne sont pas activés pour cet espace.",
    access:
      "Connectez-vous avec une adhésion active pour lire vos brouillons privés.",
    missing:
      "Ce brouillon ou cette page n’est plus disponible. Rechargez la liste.",
    failed: "Impossible de charger les brouillons. Réessayez.",
    start: "Démarrer la surveillance",
    blocked:
      "Le démarrage attend la vérification des sources officielles et du fonctionnement en direct. Les préférences enregistrées n’envoient aucun e-mail.",
    threshold: "Déclencher à partir de",
    reset: "Réinitialiser à ou en dessous de",
    rapid: "Augmentation minimale",
    hours: "heures",
    category: "Les changements de catégorie nécessitent une échelle vérifiée.",
    noRules: "Aucune règle de changement enregistrée.",
    delivery: "Préférence e-mail enregistrée",
    quiet: "Heures calmes",
    timezone: "Fuseau horaire",
    unknown: "Paramètre inconnu",
    allergens: {
      alder: "Aulne",
      birch: "Bouleau",
      hazel: "Noisetier",
      beech: "Hêtre",
      ash: "Frêne",
      oak: "Chêne",
      grasses: "Graminées",
      ragweed: "Ambroisie",
    },
    periods: {
      observation_hourly: "Observation horaire",
      observation_daily_00_24_utc: "Moyenne journalière, 00–24 UTC",
      observation_daily_06_06_utc: "Moyenne journalière, 06–06 UTC",
      forecast_instant: "Prévision à un instant donné",
    },
    email: {
      off: "Désactivé",
      immediate: "Immédiat",
      daily_digest: "Résumé quotidien",
    },
  },
  "it-CH": {
    title: "Bozze Pollen Watch",
    note: "Impostazioni private salvate. Le misurazioni di una stazione non descrivono il livello esatto di polline a casa vostra. Osservazioni e previsioni dal vivo non sono disponibili qui.",
    station: "Stazione",
    settings: "Impostazioni salvate",
    history: "Cronologia delle impostazioni",
    revision: "Revisione",
    loading: "Caricamento…",
    refresh: "Ricarica le bozze",
    more: "Carica altro",
    empty: "Nessuna bozza salvata in questo spazio.",
    select: "Selezionate una bozza per leggerne impostazioni e cronologia.",
    disabled: "Le bozze Pollen Watch non sono abilitate per questo spazio.",
    access:
      "Accedete con un’iscrizione attiva per leggere le vostre bozze private.",
    missing:
      "Questa bozza o pagina non è più disponibile. Ricaricate l’elenco.",
    failed: "Impossibile caricare le bozze. Riprovate.",
    start: "Avvia monitoraggio",
    blocked:
      "L’avvio attende la verifica delle fonti ufficiali e del flusso dal vivo. Le preferenze salvate non inviano e-mail.",
    threshold: "Attiva a partire da",
    reset: "Ripristina a o al di sotto di",
    rapid: "Aumento minimo",
    hours: "ore",
    category: "I cambiamenti di categoria richiedono una scala verificata.",
    noRules: "Nessuna regola di cambiamento salvata.",
    delivery: "Preferenza e-mail salvata",
    quiet: "Orari di silenzio",
    timezone: "Fuso orario",
    unknown: "Impostazione sconosciuta",
    allergens: {
      alder: "Ontano",
      birch: "Betulla",
      hazel: "Nocciolo",
      beech: "Faggio",
      ash: "Frassino",
      oak: "Quercia",
      grasses: "Graminacee",
      ragweed: "Ambrosia",
    },
    periods: {
      observation_hourly: "Osservazione oraria",
      observation_daily_00_24_utc: "Media giornaliera, 00–24 UTC",
      observation_daily_06_06_utc: "Media giornaliera, 06–06 UTC",
      forecast_instant: "Previsione per un istante",
    },
    email: {
      off: "Disattivata",
      immediate: "Immediata",
      daily_digest: "Riepilogo giornaliero",
    },
  },
  "rm-CH": {
    title: "Sbozs Pollen Watch",
    note: "Parameters privats memorisads. Las mesiraziuns d’ina staziun na descrivan betg il nivel exact da pollen a chasa. Observaziuns e prognosas actualas n’èn betg disponiblas qua.",
    station: "Staziun",
    settings: "Parameters memorisads",
    history: "Istorgia dals parameters",
    revision: "Versiun",
    loading: "Chargiar…",
    refresh: "Rechargiar ils sbozs",
    more: "Chargiar dapli",
    empty: "Nagins sbozs memorisads en quest spazi da lavur.",
    select: "Tscherna in sboz per leger ses parameters e sia istorgia.",
    disabled:
      "Ils sbozs Pollen Watch n’èn betg activads per quest spazi da lavur.",
    access:
      "S’annunzia cun ina commembranza activa per leger tes sbozs privats.",
    missing:
      "Quest sboz u questa pagina n’è betg pli disponibla. Rechargia la glista.",
    failed: "Ils sbozs n’han betg pudì vegnir chargiads. Emprova danovamain.",
    start: "Cumenzar la surveglianza",
    blocked:
      "Il cumenzament spetga la verificaziun da las funtaunas uffizialas e dal funcziunament actual. Las preferenzas memorisadas na tramettan nagins e-mails.",
    threshold: "Activar a partir da",
    reset: "Reinizialisar tar u sut",
    rapid: "Augment minimal",
    hours: "uras",
    category: "Midadas da categoria dovran ina scala verifitgada.",
    noRules: "Naginas reglas da midada memorisadas.",
    delivery: "Preferenza dad e-mail memorisada",
    quiet: "Uras da paus",
    timezone: "Zona d’urari",
    unknown: "Parameter nunenconuschent",
    allergens: {
      alder: "Ogn",
      birch: "Badugn",
      hazel: "Nitscholer",
      beech: "Fau",
      ash: "Fraissen",
      oak: "Ruver",
      grasses: "Graminaceas",
      ragweed: "Ambrosia",
    },
    periods: {
      observation_hourly: "Observaziun per ura",
      observation_daily_00_24_utc: "Media dal di, 00–24 UTC",
      observation_daily_06_06_utc: "Media dal di, 06–06 UTC",
      forecast_instant: "Prognosa per in mument",
    },
    email: {
      off: "Deactivà",
      immediate: "Immediat",
      daily_digest: "Resumaziun quotidiana",
    },
  },
};
