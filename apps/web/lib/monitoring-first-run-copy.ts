import type { Locale } from "./i18n";

type Copy = {
  title: string;
  body: string;
  saved: string;
  continue: string;
  steps: string;
  viewer: string;
  personal: string;
  business: string;
  legacy: string;
  company: string;
};
export const monitoringFirstRunCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "What would you like to monitor?",
    body: "Choose a starting point. We save this choice only for you in this workspace; you can change it later.",
    saved: "Your saved starting point",
    continue: "Continue setup",
    steps:
      "Choose your settings, check the preview and available sources, then select Start when ready. Email requires separate consent. Choosing a direction here does not create or activate a monitor.",
    viewer:
      "You can save a starting point and inspect the section. Your current read-only role cannot create or start monitors.",
    personal: "For everyday life",
    business: "For work",
    legacy:
      "The legal-workspace steps below record legal sources, interests and evidence. They do not verify the setup or source coverage of a Monitoring direction.",
    company:
      "Using Helvetic Lens for yourself? Leave the company field empty to create your own workspace.",
  },
  "de-CH": {
    title: "Was möchten Sie beobachten?",
    body: "Wählen Sie einen Einstieg. Diese Auswahl wird nur für Sie in diesem Arbeitsbereich gespeichert und kann später geändert werden.",
    saved: "Ihr gespeicherter Einstieg",
    continue: "Einrichtung fortsetzen",
    steps:
      "Wählen Sie die Einstellungen, prüfen Sie Vorschau und verfügbare Quellen und wählen Sie dann Start. E-Mail erfordert eine separate Einwilligung. Die Auswahl hier erstellt oder aktiviert keine Beobachtung.",
    viewer:
      "Sie können einen Einstieg speichern und den Bereich ansehen. Mit Ihrer aktuellen Leseberechtigung können Sie keine Beobachtungen erstellen oder starten.",
    personal: "Für den Alltag",
    business: "Für die Arbeit",
    legacy:
      "Die folgenden Schritte zum Rechtsbereich erfassen Rechtsquellen, Interessen und Nachweise. Sie bestätigen weder die Einrichtung noch die Quellenabdeckung eines Monitoring-Bereichs.",
    company:
      "Nutzen Sie Helvetic Lens privat? Lassen Sie das Firmenfeld leer, um Ihren eigenen Arbeitsbereich anzulegen.",
  },
  "fr-CH": {
    title: "Que souhaitez-vous surveiller ?",
    body: "Choisissez un point de départ. Ce choix est enregistré uniquement pour vous dans cet espace et peut être modifié plus tard.",
    saved: "Votre point de départ enregistré",
    continue: "Poursuivre la configuration",
    steps:
      "Choisissez vos paramètres, vérifiez l’aperçu et les sources disponibles, puis démarrez quand vous êtes prêt. Les e-mails nécessitent un consentement distinct. Le choix ici ne crée ni n’active une veille.",
    viewer:
      "Vous pouvez enregistrer un point de départ et consulter la rubrique. Votre rôle actuel en lecture seule ne permet pas de créer ou de démarrer une veille.",
    personal: "Au quotidien",
    business: "Pour le travail",
    legacy:
      "Les étapes juridiques ci-dessous enregistrent les sources, intérêts et preuves juridiques. Elles ne valident ni la configuration ni la couverture des sources d’une rubrique de veille.",
    company:
      "Vous utilisez Helvetic Lens à titre personnel ? Laissez le champ entreprise vide pour créer votre propre espace.",
  },
  "it-CH": {
    title: "Che cosa desideri monitorare?",
    body: "Scegli un punto di partenza. La scelta viene salvata solo per te in questo spazio e può essere cambiata in seguito.",
    saved: "Il tuo punto di partenza salvato",
    continue: "Continua la configurazione",
    steps:
      "Scegli le impostazioni, controlla l’anteprima e le fonti disponibili, poi avvia quando sei pronto. Le e-mail richiedono un consenso separato. La scelta qui non crea né attiva un monitoraggio.",
    viewer:
      "Puoi salvare un punto di partenza e consultare la sezione. Il tuo attuale ruolo di sola lettura non consente di creare o avviare monitoraggi.",
    personal: "Per la vita quotidiana",
    business: "Per il lavoro",
    legacy:
      "I passaggi giuridici sotto registrano fonti, interessi e prove giuridiche. Non verificano la configurazione o la copertura delle fonti di una sezione di monitoraggio.",
    company:
      "Usi Helvetic Lens per te stesso? Lascia vuoto il campo azienda per creare il tuo spazio.",
  },
  "rm-CH": {
    title: "Tge vulais Vus observar?",
    body: "Tschernei in punct da partenza. Questa tscherna vegn memorisada mo per Vus en quest spazi da lavur e po vegnir midada pli tard.",
    saved: "Voss punct da partenza memorisà",
    continue: "Cuntinuar la configuraziun",
    steps:
      "Tschernei ils parameters, controllai la prevista e las funtaunas disponiblas e cumenzai lura. E-mails dovran in consentiment separà. La tscherna qua na creescha ni activescha in monitoring.",
    viewer:
      "Vus pudais memorisar in punct da partenza e consultar la rubrica. Vossa rolla actuala da lectura na permetta betg da crear u cumenzar monitorings.",
    personal: "Per il mintgadi",
    business: "Per la lavur",
    legacy:
      "Ils pass giuridics sutvart registreschan funtaunas, interess e cumprovas giuridicas. Els na verifitgeschan betg la configuraziun u la cuvrida da funtaunas d’ina rubrica da monitoring.",
    company:
      "Duvrais Vus Helvetic Lens per sasez? Laschai vid il champ da firma per crear Voss agen spazi da lavur.",
  },
};
