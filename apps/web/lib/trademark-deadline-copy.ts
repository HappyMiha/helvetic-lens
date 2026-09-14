import type { Locale } from "./i18n";

const en = {
  title: "Opposition deadline · verify before filing",
  warning:
    "This calculation requires independent legal verification before filing or paying a fee. It does not file an opposition or contact counsel.",
  help: "Choose the legally relevant calendar for the party or representative’s domicile. Language and device location do not determine this calendar.",
  calendar: "Reviewed holiday calendar",
  basis: "Relevant domicile",
  party: "Party",
  representative: "Representative",
  choose: "Choose explicitly",
  none: "No calendar selected",
  empty:
    "No reviewed calendars are available yet. Register monitoring remains available; no legal deadline is claimed.",
  failed: "Calendars could not be loaded. Your saved choice is retained.",
  saved: "Saved calendar is currently unavailable",
  unavailable:
    "A verified calculation is unavailable. Check the publication, applicable rule and calendar with counsel.",
  context:
    "Choose a domicile calendar in the portfolio to request a calculation.",
  ruleMissing:
    "No current reviewed rule applies to this source and publication.",
  calendarMissing:
    "The selected calendar is missing, revoked, expired or lacks coverage.",
  publicationMissing:
    "An unambiguous official publication event is required; registration dates are not substituted.",
  historicalMissing:
    "The historical calculation can no longer be verified with its retained rule and calendar.",
  due: "Calculated deadline date",
  days: "Calendar days remaining",
  dayHelp: "0 means today; a negative number means the date has passed.",
  asOf: "As of",
  end: "Exclusive end instant",
  trace: "Calculation and source evidence",
  publication: "Official publication",
  national: "Swiss publication anchor",
  international: "First day of the month after the relevant WIPO publication",
  months: "Add three calendar months",
  skipped: "Move past a non-working day",
  rule: "Reviewed rule version",
  version: "Calendar version",
  citations: "Reviewed references",
  hash: "SHA-256",
  changed: "Deadline inputs changed",
};
type Copy = { [K in keyof typeof en]: string };
export const trademarkDeadlineCopy: Record<Locale, Copy> = {
  "en-CH": en,
  "de-CH": {
    title: "Widerspruchsfrist · vor Einreichung prüfen",
    warning:
      "Diese Berechnung muss vor einer Einreichung oder Gebührenzahlung unabhängig rechtlich geprüft werden. Sie reicht keinen Widerspruch ein und kontaktiert keine Rechtsberatung.",
    help: "Wählen Sie den rechtlich massgebenden Kalender am Wohnsitz der Partei oder ihrer Vertretung. Sprache und Gerätestandort bestimmen diesen Kalender nicht.",
    calendar: "Geprüfter Feiertagskalender",
    basis: "Massgebender Wohnsitz",
    party: "Partei",
    representative: "Vertretung",
    choose: "Ausdrücklich wählen",
    none: "Kein Kalender gewählt",
    empty:
      "Noch keine geprüften Kalender verfügbar. Die Registerüberwachung bleibt verfügbar; eine Rechtsfrist wird nicht angegeben.",
    failed:
      "Kalender konnten nicht geladen werden. Ihre gespeicherte Auswahl bleibt erhalten.",
    saved: "Gespeicherter Kalender derzeit nicht verfügbar",
    unavailable:
      "Keine verifizierte Berechnung verfügbar. Prüfen Sie Publikation, Regel und Kalender mit einer Rechtsberatung.",
    context:
      "Wählen Sie im Portfolio einen Wohnsitzkalender für die Berechnung.",
    ruleMissing:
      "Keine aktuelle geprüfte Regel gilt für diese Quelle und Publikation.",
    calendarMissing:
      "Der gewählte Kalender fehlt, ist widerrufen, abgelaufen oder deckt den Zeitraum nicht ab.",
    publicationMissing:
      "Ein eindeutiges amtliches Publikationsereignis ist erforderlich; Eintragungsdaten werden nicht ersatzweise verwendet.",
    historicalMissing:
      "Die historische Berechnung lässt sich mit der hinterlegten Regel und dem Kalender nicht mehr verifizieren.",
    due: "Berechnetes Fristdatum",
    days: "Verbleibende Kalendertage",
    dayHelp:
      "0 bedeutet heute; eine negative Zahl bedeutet, dass das Datum verstrichen ist.",
    asOf: "Stand",
    end: "Exklusiver Endzeitpunkt",
    trace: "Berechnung und Quellenbelege",
    publication: "Amtliche Publikation",
    national: "Ausgangspunkt Schweizer Publikation",
    international:
      "Erster Tag des Monats nach der massgebenden WIPO-Publikation",
    months: "Drei Kalendermonate hinzufügen",
    skipped: "Arbeitsfreien Tag überspringen",
    rule: "Geprüfte Regelversion",
    version: "Kalenderversion",
    citations: "Geprüfte Referenzen",
    hash: "SHA-256",
    changed: "Fristgrundlagen geändert",
  },
  "fr-CH": {
    title: "Délai d’opposition · vérifier avant le dépôt",
    warning:
      "Ce calcul doit faire l’objet d’une vérification juridique indépendante avant tout dépôt ou paiement. Il ne dépose pas d’opposition et ne contacte aucun conseil.",
    help: "Choisissez le calendrier juridiquement pertinent du domicile de la partie ou de son représentant. La langue et la position de l’appareil ne le déterminent pas.",
    calendar: "Calendrier des jours fériés vérifié",
    basis: "Domicile pertinent",
    party: "Partie",
    representative: "Représentant",
    choose: "Choisir explicitement",
    none: "Aucun calendrier choisi",
    empty:
      "Aucun calendrier vérifié disponible. La surveillance du registre reste accessible ; aucun délai juridique n’est affirmé.",
    failed:
      "Impossible de charger les calendriers. Votre choix enregistré est conservé.",
    saved: "Calendrier enregistré actuellement indisponible",
    unavailable:
      "Calcul vérifié indisponible. Vérifiez la publication, la règle et le calendrier avec un conseil juridique.",
    context:
      "Choisissez un calendrier de domicile dans le portefeuille pour demander le calcul.",
    ruleMissing:
      "Aucune règle vérifiée actuelle ne s’applique à cette source et publication.",
    calendarMissing:
      "Le calendrier choisi est absent, révoqué, expiré ou ne couvre pas la période.",
    publicationMissing:
      "Un événement de publication officielle non ambigu est requis ; la date d’enregistrement ne le remplace pas.",
    historicalMissing:
      "Le calcul historique ne peut plus être vérifié avec la règle et le calendrier conservés.",
    due: "Date limite calculée",
    days: "Jours calendaires restants",
    dayHelp:
      "0 signifie aujourd’hui ; un nombre négatif signifie que la date est passée.",
    asOf: "Au",
    end: "Instant de fin exclusif",
    trace: "Calcul et preuves des sources",
    publication: "Publication officielle",
    national: "Point de départ de la publication suisse",
    international:
      "Premier jour du mois suivant la publication OMPI pertinente",
    months: "Ajouter trois mois calendaires",
    skipped: "Reporter après un jour non ouvrable",
    rule: "Version de la règle vérifiée",
    version: "Version du calendrier",
    citations: "Références vérifiées",
    hash: "SHA-256",
    changed: "Bases du délai modifiées",
  },
  "it-CH": {
    title: "Termine di opposizione · verificare prima del deposito",
    warning:
      "Questo calcolo richiede una verifica giuridica indipendente prima del deposito o del pagamento. Non presenta opposizioni e non contatta consulenti.",
    help: "Scegliere il calendario giuridicamente pertinente al domicilio della parte o del rappresentante. La lingua e la posizione del dispositivo non lo determinano.",
    calendar: "Calendario festivo verificato",
    basis: "Domicilio pertinente",
    party: "Parte",
    representative: "Rappresentante",
    choose: "Scegliere esplicitamente",
    none: "Nessun calendario scelto",
    empty:
      "Nessun calendario verificato disponibile. Il monitoraggio del registro rimane disponibile; non viene indicato un termine legale.",
    failed:
      "Impossibile caricare i calendari. La scelta salvata viene conservata.",
    saved: "Calendario salvato attualmente non disponibile",
    unavailable:
      "Calcolo verificato non disponibile. Verificare pubblicazione, regola e calendario con un consulente legale.",
    context:
      "Scegliere un calendario del domicilio nel portafoglio per richiedere il calcolo.",
    ruleMissing:
      "Nessuna regola verificata attuale si applica a questa fonte e pubblicazione.",
    calendarMissing:
      "Il calendario scelto è assente, revocato, scaduto o non copre il periodo.",
    publicationMissing:
      "È richiesto un evento di pubblicazione ufficiale univoco; la data di registrazione non lo sostituisce.",
    historicalMissing:
      "Il calcolo storico non è più verificabile con la regola e il calendario conservati.",
    due: "Data del termine calcolata",
    days: "Giorni di calendario rimanenti",
    dayHelp:
      "0 indica oggi; un numero negativo indica che la data è trascorsa.",
    asOf: "Al",
    end: "Istante finale esclusivo",
    trace: "Calcolo e prove delle fonti",
    publication: "Pubblicazione ufficiale",
    national: "Decorrenza della pubblicazione svizzera",
    international:
      "Primo giorno del mese dopo la pubblicazione OMPI pertinente",
    months: "Aggiungere tre mesi di calendario",
    skipped: "Superare un giorno non lavorativo",
    rule: "Versione della regola verificata",
    version: "Versione del calendario",
    citations: "Riferimenti verificati",
    hash: "SHA-256",
    changed: "Basi del termine modificate",
  },
  "rm-CH": {
    title: "Termin d’opposiziun · verifitgar avant l’inoltraziun",
    warning:
      "Quest calcul sto vegnir verifitgà independentamain dal puntg da vista giuridic avant ina inoltraziun u in pajament. El na inoltra nagina opposiziun e na contactescha nagin cussegl.",
    help: "Tscherna il chalender giuridicamain relevant dal domicil da la partida u da sia represchentanza. La lingua e la posiziun dal dispositiv na determineschan betg il chalender.",
    calendar: "Chalender da firads verifitgà",
    basis: "Domicil relevant",
    party: "Partida",
    representative: "Represchentanza",
    choose: "Tscherner explicitamain",
    none: "Nagin chalender tschernì",
    empty:
      "Anc nagins chalenders verifitgads disponibels. L’observaziun dal register resta disponibla; nagin termin giuridic vegn inditgà.",
    failed:
      "Ils chalenders n’han betg pudì vegnir chargiads. La tscherna memorisada resta mantegnida.",
    saved: "Chalender memorisà actualmain betg disponibel",
    unavailable:
      "Nagin calcul verifitgà disponibel. Verifitgescha la publicaziun, la regla ed il chalender cun in cussegl giuridic.",
    context:
      "Tscherna in chalender dal domicil en il portfolio per dumandar il calcul.",
    ruleMissing:
      "Nagina regla actuala verifitgada vala per questa funtauna e publicaziun.",
    calendarMissing:
      "Il chalender tschernì manca, è revocà, scadì u na cuvra betg il temp.",
    publicationMissing:
      "In eveniment da publicaziun uffiziala cler è necessari; datas da registraziun na vegnan betg duvradas sco remplazzament.",
    historicalMissing:
      "Il calcul istoric na po betg pli vegnir verifitgà cun la regla ed il chalender conservads.",
    due: "Data dal termin calculada",
    days: "Dis da chalender restants",
    dayHelp: "0 munta oz; in dumber negativ munta che la data è passada.",
    asOf: "Stadi dals",
    end: "Mument final exclusiv",
    trace: "Calcul e cumprovas da las funtaunas",
    publication: "Publicaziun uffiziala",
    national: "Punct da partenza da la publicaziun svizra",
    international: "Emprim di dal mais suenter la publicaziun OMPI relevanta",
    months: "Agiuntar trais mais da chalender",
    skipped: "Surpassar in di betg lavurativ",
    rule: "Versiun da la regla verifitgada",
    version: "Versiun dal chalender",
    citations: "Referenzas verifitgadas",
    hash: "SHA-256",
    changed: "Basas dal termin midadas",
  },
};

export function deadlineReason(locale: Locale, reason?: string | null) {
  const c = trademarkDeadlineCopy[locale];
  if (reason === "deadline_context_required") return c.context;
  if (reason?.includes("historical") || reason?.includes("binding"))
    return c.historicalMissing;
  if (reason?.includes("calendar")) return c.calendarMissing;
  if (reason?.includes("publication")) return c.publicationMissing;
  if (reason?.includes("rule")) return c.ruleMissing;
  return c.unavailable;
}
