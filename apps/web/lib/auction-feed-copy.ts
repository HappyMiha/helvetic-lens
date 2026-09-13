import type { Locale } from "./i18n";

const en = {
  today: "Auction updates",
  inbox: "Auction changes to review",
  empty: "No current unread auction changes on this page.",
  scope:
    "Your private auction changes. Source coverage may be incomplete; an empty list is not an all-clear.",
  unavailable:
    "Some saved changes cannot be shown with current source evidence. Open Auction Watch to check the source.",
  open: "Open change and review",
  detected: "Change detected",
  selected: "Saved auction change",
  before: "Before this change",
  after: "At this change",
  current: "Current lot and private decision",
  newer: "A newer material change is available. Review the current lot below.",
  profile:
    "This change used an earlier profile revision. Current matching uses your latest settings.",
  first: "First saved match; no previous version.",
  new_match: "New matching lot",
  price_above_limit: "Price crossed your budget limit",
  price_changed: "Published price changed",
  deadline_changed: "Auction end changed",
  start_changed: "Auction start changed",
  cancelled: "Auction cancelled",
  status_changed: "Official status changed",
  asset_details_changed: "Asset details changed",
  conditions: "Conditions or their evidence changed",
  documents: "Document set or its evidence changed",
  source_evidence_gap: "Source evidence has a gap",
  profile_changed: "Profile changed",
  other: "Saved auction change",
};
type Copy = Record<keyof typeof en, string>;
export const auctionFeedCopy: Record<Locale, Copy> = {
  "en-CH": en,
  "de-CH": {
    today: "Auktionsänderungen",
    inbox: "Auktionsänderungen zur Prüfung",
    empty: "Keine aktuellen ungelesenen Auktionsänderungen auf dieser Seite.",
    scope:
      "Ihre privaten Auktionsänderungen. Die Quellenabdeckung kann unvollständig sein; eine leere Liste ist keine Entwarnung.",
    unavailable:
      "Einige gespeicherte Änderungen lassen sich nicht mit aktuellen Quellenbelegen anzeigen. Prüfen Sie die Quelle in Auction Watch.",
    open: "Änderung öffnen und prüfen",
    detected: "Änderung erkannt",
    selected: "Gespeicherte Auktionsänderung",
    before: "Vor dieser Änderung",
    after: "Bei dieser Änderung",
    current: "Aktuelles Los und private Entscheidung",
    newer:
      "Eine neuere wesentliche Änderung liegt vor. Prüfen Sie unten das aktuelle Los.",
    profile:
      "Diese Änderung verwendete eine frühere Profilversion. Der aktuelle Abgleich nutzt Ihre neuesten Einstellungen.",
    first: "Erster gespeicherter Treffer; keine frühere Version.",
    new_match: "Neues passendes Los",
    price_above_limit: "Preis hat Ihre Budgetgrenze überschritten",
    price_changed: "Veröffentlichter Preis geändert",
    deadline_changed: "Auktionsende geändert",
    start_changed: "Auktionsbeginn geändert",
    cancelled: "Auktion abgesagt",
    status_changed: "Offizieller Status geändert",
    asset_details_changed: "Angaben zum Objekt geändert",
    conditions: "Bedingungen oder deren Belege geändert",
    documents: "Dokumentbestand oder dessen Belege geändert",
    source_evidence_gap: "Lücke in den Quellenbelegen",
    profile_changed: "Profil geändert",
    other: "Gespeicherte Auktionsänderung",
  },
  "fr-CH": {
    today: "Actualités des enchères",
    inbox: "Changements d’enchères à examiner",
    empty: "Aucun changement d’enchère actuel non lu sur cette page.",
    scope:
      "Vos changements d’enchères privés. La couverture des sources peut être incomplète ; une liste vide ne signifie pas absence de problème.",
    unavailable:
      "Certains changements enregistrés ne disposent pas de preuves actuelles affichables. Vérifiez la source dans Auction Watch.",
    open: "Ouvrir le changement et examiner",
    detected: "Changement détecté",
    selected: "Changement d’enchère enregistré",
    before: "Avant ce changement",
    after: "Lors de ce changement",
    current: "Lot actuel et décision privée",
    newer:
      "Un changement important plus récent est disponible. Examinez le lot actuel ci-dessous.",
    profile:
      "Ce changement utilisait une ancienne version du profil. La correspondance actuelle utilise vos derniers réglages.",
    first: "Première correspondance enregistrée ; aucune version précédente.",
    new_match: "Nouveau lot correspondant",
    price_above_limit: "Le prix a dépassé votre budget",
    price_changed: "Prix publié modifié",
    deadline_changed: "Fin de l’enchère modifiée",
    start_changed: "Début de l’enchère modifié",
    cancelled: "Enchère annulée",
    status_changed: "Statut officiel modifié",
    asset_details_changed: "Détails du bien modifiés",
    conditions: "Conditions ou preuves associées modifiées",
    documents: "Documents ou preuves associées modifiés",
    source_evidence_gap: "Lacune dans les preuves de la source",
    profile_changed: "Profil modifié",
    other: "Changement d’enchère enregistré",
  },
  "it-CH": {
    today: "Aggiornamenti delle aste",
    inbox: "Modifiche delle aste da esaminare",
    empty: "Nessuna modifica attuale non letta delle aste in questa pagina.",
    scope:
      "Le tue modifiche private delle aste. La copertura delle fonti può essere incompleta; una lista vuota non conferma l’assenza di problemi.",
    unavailable:
      "Alcune modifiche salvate non hanno prove attuali visualizzabili. Verifica la fonte in Auction Watch.",
    open: "Apri la modifica ed esamina",
    detected: "Modifica rilevata",
    selected: "Modifica dell’asta salvata",
    before: "Prima di questa modifica",
    after: "Al momento della modifica",
    current: "Lotto attuale e decisione privata",
    newer:
      "È disponibile una modifica rilevante più recente. Esamina il lotto attuale qui sotto.",
    profile:
      "Questa modifica usava una versione precedente del profilo. La corrispondenza attuale usa le ultime impostazioni.",
    first: "Prima corrispondenza salvata; nessuna versione precedente.",
    new_match: "Nuovo lotto corrispondente",
    price_above_limit: "Il prezzo ha superato il tuo budget",
    price_changed: "Prezzo pubblicato modificato",
    deadline_changed: "Fine dell’asta modificata",
    start_changed: "Inizio dell’asta modificato",
    cancelled: "Asta annullata",
    status_changed: "Stato ufficiale modificato",
    asset_details_changed: "Dettagli del bene modificati",
    conditions: "Condizioni o relative prove modificate",
    documents: "Documenti o relative prove modificati",
    source_evidence_gap: "Lacuna nelle prove della fonte",
    profile_changed: "Profilo modificato",
    other: "Modifica dell’asta salvata",
  },
  "rm-CH": {
    today: "Actualisaziuns dals inchants",
    inbox: "Midadas d’inchants da controllar",
    empty:
      "Naginas midadas actualas betg legidas dals inchants sin questa pagina.",
    scope:
      "Vossas midadas privatas d’inchants. La cuvrida da las funtaunas po esser incumpletta; ina glista vida na conferma betg l’absenza da problems.",
    unavailable:
      "Intginas midadas memorisadas n’han naginas cumprovas actualas mussablas. Controllai la funtauna en Auction Watch.",
    open: "Avrir e controllar la midada",
    detected: "Midada constatada",
    selected: "Midada d’inchant memorisada",
    before: "Avant questa midada",
    after: "Tar questa midada",
    current: "Lot actual e decisiun privata",
    newer:
      "Ina midada relevanta pli nova è disponibla. Controllai il lot actual sutvart.",
    profile:
      "Questa midada duvrava ina versiun precedenta dal profil. La cumparegliaziun actuala dovra Voss ultims parameters.",
    first: "Emprima correspundenza memorisada; nagina versiun precedenta.",
    new_match: "Nov lot correspundent",
    price_above_limit: "Il pretsch ha surpassà Voss budget",
    price_changed: "Pretsch publitgà midà",
    deadline_changed: "Fin da l’inchant midada",
    start_changed: "Cumenzament da l’inchant midà",
    cancelled: "Inchant annullà",
    status_changed: "Status uffizial midà",
    asset_details_changed: "Detagls dal bain midads",
    conditions: "Cundiziuns u lur cumprovas midadas",
    documents: "Documents u lur cumprovas midadas",
    source_evidence_gap: "Lacuna en las cumprovas da la funtauna",
    profile_changed: "Profil midà",
    other: "Midada d’inchant memorisada",
  },
};

export function auctionChangeLabel(locale: Locale, code: string) {
  const copy = auctionFeedCopy[locale];
  if (code.startsWith("document_")) return copy.documents;
  if (code.startsWith("conditions_")) return copy.conditions;
  const supported = [
    "new_match",
    "price_above_limit",
    "price_changed",
    "deadline_changed",
    "start_changed",
    "cancelled",
    "status_changed",
    "asset_details_changed",
    "source_evidence_gap",
    "profile_changed",
  ];
  return supported.includes(code) ? copy[code as keyof Copy] : copy.other;
}
