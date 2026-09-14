import type { Locale } from "./i18n";
import { riverCopy } from "./river-copy";

const extra = {
  title: "Air Quality Watch",
  intro:
    "Private station monitoring. Material changes appear here and in Today. Choose email delivery in monitor settings.",
  station: "Supported station",
  metrics: "Pollutants",
  O3: "Ozone (O₃)",
  NO2: "Nitrogen dioxide (NO₂)",
  PM10: "PM10",
  PM25: "PM2.5",
  hourly_mean: "Hourly mean",
  daily_mean: "Official daily mean",
  daily_max_hourly: "Official daily maximum of hourly ozone means",
  sourceDate: "Source calendar date",
  dailyHelp:
    "Daily reports describe completed days. Ozone uses the highest hourly mean, other pollutants the daily mean. Hourly conditions may differ; an older report is shown as stale.",
  rolling_24h_mean: "Calculated mean of 24 consecutive hourly values",
  period: "Measurement period",
  hysteresis: "Improvement margin (µg/m³)",
  cooldown: "Minimum time between deteriorations (hours)",
  ruleHelp:
    "Above the threshold triggers a change. Improvement is reported at or below threshold minus the margin. Cooldown suppresses repeated deteriorations; improvements remain visible.",
  scope:
    "Basel-Binningen (suburban) and Lugano-Università (urban). These stations represent their surroundings, not every neighbourhood. Current source availability is shown here.",
  limits:
    "Provisional observations, not personal health advice. Missing data means unknown. History: 30 days; recovery: 72 hours. Only complete hourly inputs are used for a calculated 24-hour mean.",
  derived: "Calculated by Helvetic Lens from official hourly observations",
  corrected: "Source correction",
  missing: "Missing",
  invalid:
    "Choose a station, name and pollutants, and check thresholds, margins and periods.",
  incomplete_window: "Incomplete 24-hour window",
  mute: "Mute pollutant",
  unmute: "Unmute pollutant",
  muted: "Muted",
  threshold_crossed: "Pollution threshold exceeded",
  threshold_cleared: "Pollution improved below your threshold",
  license: "Source reuse terms",
  attribution: "Kanton Basel-Stadt · Basel-Binningen · MeteoSchweiz / NABEL",
  why: "You monitor this station, pollutant and measurement period.",
  open: "Open monitor",
  today: "Air quality changes",
  previous: "Previous observation",
  currentValue: "Current observation",
  noMatch: "No supported station matches this search.",
};
type Extra = Record<keyof typeof extra, string>;
const translations: Record<Locale, Extra> = {
  "en-CH": extra,
  "de-CH": {
    title: "Luftqualitäts-Monitoring",
    intro:
      "Privates Stationsmonitoring. Wesentliche Änderungen erscheinen hier und unter Heute. Wählen Sie E-Mail in den Monitoreinstellungen.",
    station: "Unterstützte Station",
    metrics: "Schadstoffe",
    O3: "Ozon (O₃)",
    NO2: "Stickstoffdioxid (NO₂)",
    PM10: "PM10",
    PM25: "PM2.5",
    hourly_mean: "Stundenmittel",
    daily_mean: "Offizielles Tagesmittel",
    daily_max_hourly: "Offizielles Tagesmaximum der Ozon-Stundenmittel",
    sourceDate: "Kalenderdatum der Quelle",
    dailyHelp:
      "Tagesberichte beschreiben abgeschlossene Tage. Ozon verwendet das höchste Stundenmittel, andere Schadstoffe das Tagesmittel. Stundenwerte können abweichen; ältere Berichte werden als veraltet angezeigt.",
    rolling_24h_mean: "Mittel aus 24 aufeinanderfolgenden Stundenwerten",
    period: "Messzeitraum",
    hysteresis: "Verbesserungsabstand (µg/m³)",
    cooldown: "Mindestabstand zwischen Verschlechterungen (Stunden)",
    ruleHelp:
      "Über der Schwelle wird eine Änderung gemeldet. Verbesserung gilt bei höchstens Schwelle minus Abstand. Die Wartezeit unterdrückt wiederholte Verschlechterungen; Verbesserungen bleiben sichtbar.",
    scope:
      "Basel-Binningen (vorstädtisch) und Lugano-Università (städtisch). Die Stationen repräsentieren ihre Umgebung, nicht jedes Quartier. Die aktuelle Quellenverfügbarkeit wird hier angezeigt.",
    limits:
      "Vorläufige Messungen, keine persönliche Gesundheitsberatung. Fehlende Daten bleiben unbekannt. Historie: 30 Tage; Wiederherstellung: 72 Stunden. Ein berechnetes 24-Stunden-Mittel erfordert vollständige Stundenwerte.",
    derived: "Von Helvetic Lens aus amtlichen Stundenwerten berechnet",
    corrected: "Quellenkorrektur",
    missing: "Fehlend",
    invalid:
      "Station, Name und Schadstoffe wählen und Schwellen, Abstände und Zeiträume prüfen.",
    incomplete_window: "Unvollständiges 24-Stunden-Fenster",
    mute: "Schadstoff stummschalten",
    unmute: "Schadstoff wieder aktivieren",
    muted: "Stummgeschaltet",
    threshold_crossed: "Schadstoffschwelle überschritten",
    threshold_cleared: "Belastung unter Ihre Schwelle gesunken",
    license: "Nutzungsbedingungen der Quelle",
    attribution: "Kanton Basel-Stadt · Basel-Binningen · MeteoSchweiz / NABEL",
    why: "Sie beobachten diese Station, diesen Schadstoff und diesen Messzeitraum.",
    open: "Monitoring öffnen",
    today: "Änderungen der Luftqualität",
    previous: "Vorherige Messung",
    currentValue: "Aktuelle Messung",
    noMatch: "Keine unterstützte Station passt zur Suche.",
  },
  "fr-CH": {
    title: "Suivi de la qualité de l’air",
    intro:
      "Suivi privé des stations. Les changements significatifs apparaissent ici et dans Aujourd’hui. Choisissez les e-mails dans les réglages du suivi.",
    station: "Station prise en charge",
    metrics: "Polluants",
    O3: "Ozone (O₃)",
    NO2: "Dioxyde d’azote (NO₂)",
    PM10: "PM10",
    PM25: "PM2.5",
    hourly_mean: "Moyenne horaire",
    daily_mean: "Moyenne journalière officielle",
    daily_max_hourly:
      "Maximum journalier officiel des moyennes horaires d’ozone",
    sourceDate: "Date civile de la source",
    dailyHelp:
      "Les rapports journaliers décrivent des jours terminés. L’ozone utilise la moyenne horaire maximale, les autres polluants la moyenne journalière. Les conditions horaires peuvent différer ; un rapport ancien est signalé comme périmé.",
    rolling_24h_mean: "Moyenne de 24 valeurs horaires consécutives",
    period: "Période de mesure",
    hysteresis: "Marge d’amélioration (µg/m³)",
    cooldown: "Délai minimal entre dégradations (heures)",
    ruleHelp:
      "Un dépassement du seuil déclenche un changement. L’amélioration est signalée au seuil moins la marge ou en dessous. Le délai limite les dégradations répétées ; les améliorations restent visibles.",
    scope:
      "Basel-Binningen (périurbaine) et Lugano-Università (urbaine). Ces stations représentent leurs alentours, pas chaque quartier. La disponibilité actuelle des sources est indiquée ici.",
    limits:
      "Mesures provisoires, sans conseil médical individuel. Les données manquantes restent inconnues. Historique : 30 jours ; récupération : 72 heures. Une moyenne calculée sur 24 heures exige toutes les valeurs horaires.",
    derived:
      "Calculé par Helvetic Lens à partir des observations horaires officielles",
    corrected: "Correction de la source",
    missing: "Manquant",
    invalid:
      "Choisissez station, nom et polluants, puis vérifiez seuils, marges et périodes.",
    incomplete_window: "Fenêtre de 24 heures incomplète",
    mute: "Suspendre le polluant",
    unmute: "Réactiver le polluant",
    muted: "Suspendu",
    threshold_crossed: "Seuil de pollution dépassé",
    threshold_cleared: "Pollution redescendue sous votre seuil",
    license: "Conditions de réutilisation de la source",
    attribution: "Canton de Bâle-Ville · Basel-Binningen · MétéoSuisse / NABEL",
    why: "Vous suivez cette station, ce polluant et cette période de mesure.",
    open: "Ouvrir le suivi",
    today: "Changements de qualité de l’air",
    previous: "Observation précédente",
    currentValue: "Observation actuelle",
    noMatch: "Aucune station prise en charge ne correspond à la recherche.",
  },
  "it-CH": {
    title: "Monitoraggio della qualità dell’aria",
    intro:
      "Monitoraggio privato delle stazioni. Le variazioni rilevanti appaiono qui e in Oggi. Scegli le e-mail nelle impostazioni del monitoraggio.",
    station: "Stazione supportata",
    metrics: "Inquinanti",
    O3: "Ozono (O₃)",
    NO2: "Diossido di azoto (NO₂)",
    PM10: "PM10",
    PM25: "PM2.5",
    hourly_mean: "Media oraria",
    daily_mean: "Media giornaliera ufficiale",
    daily_max_hourly:
      "Massimo giornaliero ufficiale delle medie orarie dell’ozono",
    sourceDate: "Data di calendario della fonte",
    dailyHelp:
      "I rapporti giornalieri descrivono giorni conclusi. Per l’ozono si usa la media oraria più alta, per gli altri inquinanti la media giornaliera. Le condizioni orarie possono differire; un rapporto vecchio è indicato come non aggiornato.",
    rolling_24h_mean: "Media di 24 valori orari consecutivi",
    period: "Periodo di misura",
    hysteresis: "Margine di miglioramento (µg/m³)",
    cooldown: "Intervallo minimo tra peggioramenti (ore)",
    ruleHelp:
      "Il superamento della soglia genera una variazione. Il miglioramento è segnalato alla soglia meno il margine o al di sotto. L’intervallo limita i peggioramenti ripetuti; i miglioramenti restano visibili.",
    scope:
      "Basel-Binningen (suburbana) e Lugano-Università (urbana). Le stazioni rappresentano i dintorni, non ogni quartiere. Qui è indicata la disponibilità attuale delle fonti.",
    limits:
      "Misure provvisorie, senza consigli sanitari individuali. I dati mancanti restano sconosciuti. Storico: 30 giorni; recupero: 72 ore. Una media calcolata su 24 ore richiede tutti i valori orari.",
    derived: "Calcolato da Helvetic Lens dalle osservazioni orarie ufficiali",
    corrected: "Correzione della fonte",
    missing: "Mancante",
    invalid:
      "Scegliere stazione, nome e inquinanti e verificare soglie, margini e periodi.",
    incomplete_window: "Finestra di 24 ore incompleta",
    mute: "Silenzia inquinante",
    unmute: "Riattiva inquinante",
    muted: "Silenziato",
    threshold_crossed: "Soglia di inquinamento superata",
    threshold_cleared: "Inquinamento migliorato sotto la soglia",
    license: "Condizioni di riutilizzo della fonte",
    attribution:
      "Cantone di Basilea Città · Basel-Binningen · MeteoSvizzera / NABEL",
    why: "Segui questa stazione, questo inquinante e questo periodo di misura.",
    open: "Apri monitoraggio",
    today: "Variazioni della qualità dell’aria",
    previous: "Osservazione precedente",
    currentValue: "Osservazione attuale",
    noMatch: "Nessuna stazione supportata corrisponde alla ricerca.",
  },
  "rm-CH": {
    title: "Monitoring da la qualitad da l’aria",
    intro:
      "Monitoring privat da staziuns. Midadas relevantas cumparan qua ed en Oz. Tscherna e-mails en ils parameters da l’observaziun.",
    station: "Staziun sustegnida",
    metrics: "Substanzas nuschaivlas",
    O3: "Ozon (O₃)",
    NO2: "Dioxid d’azot (NO₂)",
    PM10: "PM10",
    PM25: "PM2.5",
    hourly_mean: "Media orara",
    daily_mean: "Media quotidiana uffiziala",
    daily_max_hourly: "Maximum quotidian uffizial da las medias oraras d’ozon",
    sourceDate: "Data da chalender da la funtauna",
    dailyHelp:
      "Ils rapports quotidians descrivan dis terminads. Per l’ozon vala la media orara la pli auta, per autras substanzas la media quotidiana. Las cundiziuns oraras pon variar; rapports pli vegls vegnan inditgads sco antiquads.",
    rolling_24h_mean: "Media da 24 valurs oraras consecutivas",
    period: "Perioda da mesiraziun",
    hysteresis: "Distanza da meglieraziun (µg/m³)",
    cooldown: "Interval minimal tranter pegiuraziuns (uras)",
    ruleHelp:
      "Sur la sava vegn annunziada ina midada. La meglieraziun vala tar la sava minus la distanza u sut quella. L’interval reducescha pegiuraziuns repetidas; meglieraziuns restan visiblas.",
    scope:
      "Basel-Binningen (suburbana) e Lugano-Università (urbana). Las staziuns represchentan lur conturns, betg mintga quartier. La disponibladad actuala da las funtaunas vegn mussada qua.",
    limits:
      "Mesiraziuns provisoricas, nagin cussegl da sanadad individual. Datas mancantas restan nunenconuschentas. Istorgia: 30 dis; recuperaziun: 72 uras. Ina media calculada da 24 uras pretenda tut las valurs oraras.",
    derived: "Calculà da Helvetic Lens cun observaziuns oraras uffizialas",
    corrected: "Correctura da la funtauna",
    missing: "Mancant",
    invalid:
      "Tscherner staziun, num e substanzas e controllar savas, distanzas e periodas.",
    incomplete_window: "Fanestrà da 24 uras incumplet",
    mute: "Metter la substanza sin silenzi",
    unmute: "Reactivar la substanza",
    muted: "Sin silenzi",
    threshold_crossed: "Sava da polluziun surpassada",
    threshold_cleared: "Polluziun meglierada sut la sava",
    license: "Cundiziuns da reutilisaziun da la funtauna",
    attribution:
      "Chantun Basilea-Citad · Basel-Binningen · MeteoSvizra / NABEL",
    why: "Vus observais questa staziun, questa substanza e questa perioda da mesiraziun.",
    open: "Avrir il monitoring",
    today: "Midadas da la qualitad da l’aria",
    previous: "Observaziun precedenta",
    currentValue: "Observaziun actuala",
    noMatch: "Nag ina staziun sustegnida correspunda a la tschertga.",
  },
};
export const airCopy = Object.fromEntries(
  Object.entries(translations).map(([locale, copy]) => [
    locale,
    { ...riverCopy[locale as Locale], ...copy },
  ]),
) as Record<Locale, (typeof riverCopy)["en-CH"] & Extra>;
