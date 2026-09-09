import type { Locale } from "./i18n";

type Copy = {
  dataset: string;
  matched: string;
  separate: string;
  title: string;
  intro: string;
  open: string;
  sources: string;
  enable: string;
  collect: string;
  queued: string;
  interest: string;
  name: string;
  terms: string;
  exclusions: string;
  termsHelp: string;
  privacy: string;
  building: string;
  preview: string;
  save: string;
  saved: string;
  evidence: string;
  source: string;
  empty: string;
  scope: string;
  retry: string;
  viewer: string;
  existing: string;
  manage: string;
  notifications: string;
  back: string;
};
export const baselCopy: Record<Locale, Copy> = {
  "en-CH": {
    dataset: "Official dataset and attribution",
    matched: "Matching terms",
    separate: "Cantonal pilot · enabled separately from the federal starter",
    title: "Start with Basel-Stadt",
    intro:
      "Choose an interest, inspect a matching saved law and decide what to monitor. No AI is needed for these steps.",
    open: "Open the Basel-Stadt guide",
    sources: "1. Review and enable the source package",
    enable: "Enable Basel-Stadt for this organization",
    collect: "Collect the two starter laws",
    queued:
      "Collection was requested recently or is queued. Refresh the preview shortly; a running worker and an available official source are required.",
    interest: "2. Describe your interest",
    name: "Interest name",
    terms: "German search concepts, separated by commas",
    exclusions: "Excluded concepts, separated by commas",
    termsHelp:
      "The source texts are German. Edit the suggested terms; matching uses these terms and source metadata, not a legal interpretation.",
    privacy: "Data protection",
    building: "Building and planning",
    preview: "Preview saved matches",
    save: "Save this monitoring topic for the organization",
    saved:
      "Monitoring topic saved. Open the source evidence below; review notifications separately.",
    evidence: "Open saved evidence",
    source: "Publisher version",
    empty:
      "No match in the inspected saved sample. Collect the starter laws, refresh or refine the concepts. This does not mean no relevant law exists.",
    scope:
      "This preview inspects at most 500 saved events and shows at most 10 matches. Discovery time is not a legal change date. New source collection may still be pending.",
    retry: "Refresh",
    viewer:
      "You can inspect saved sources and preview interests. An organization administrator enables packages and saves shared monitoring topics.",
    existing:
      "An equivalent monitoring topic already exists. Review it before creating another.",
    manage: "Manage monitoring topics",
    notifications: "Choose notification preferences",
    back: "Back to getting started",
  },
  "de-CH": {
    dataset: "Amtlicher Datensatz und Quellenangabe",
    matched: "Passende Begriffe",
    separate: "Kantonaler Pilot · separat vom Bundes-Starter aktiviert",
    title: "Mit Basel-Stadt beginnen",
    intro:
      "Wählen Sie ein Interesse, prüfen Sie einen passenden gespeicherten Erlass und entscheiden Sie, was Sie überwachen möchten. Diese Schritte benötigen keine KI.",
    open: "Basel-Stadt-Einstieg öffnen",
    sources: "1. Quellenpaket prüfen und aktivieren",
    enable: "Basel-Stadt für diese Organisation aktivieren",
    collect: "Die zwei Einstiegserlasse abrufen",
    queued:
      "Der Abruf wurde kürzlich angefordert oder ist eingereiht. Aktualisieren Sie die Vorschau in Kürze; ein laufender Worker und eine verfügbare amtliche Quelle sind erforderlich.",
    interest: "2. Ihr Interesse beschreiben",
    name: "Name des Interesses",
    terms: "Deutsche Suchbegriffe, durch Kommas getrennt",
    exclusions: "Ausgeschlossene Begriffe, durch Kommas getrennt",
    termsHelp:
      "Die Quelltexte sind deutsch. Passen Sie die vorgeschlagenen Begriffe an; Treffer beruhen auf Begriffen und Quellenmetadaten, nicht auf einer rechtlichen Auslegung.",
    privacy: "Datenschutz",
    building: "Bauen und Planung",
    preview: "Gespeicherte Treffer prüfen",
    save: "Dieses Monitoring-Thema für die Organisation speichern",
    saved:
      "Monitoring-Thema gespeichert. Öffnen Sie unten den Quellenbeleg; Benachrichtigungen wählen Sie separat.",
    evidence: "Gespeicherten Beleg öffnen",
    source: "Fassung beim Herausgeber",
    empty:
      "Kein Treffer in der geprüften gespeicherten Stichprobe. Rufen Sie die Einstiegserlasse ab, aktualisieren Sie oder passen Sie die Begriffe an. Dies bedeutet nicht, dass kein relevanter Erlass existiert.",
    scope:
      "Die Vorschau prüft höchstens 500 gespeicherte Ereignisse und zeigt höchstens 10 Treffer. Der Erkennungszeitpunkt ist kein Rechtsänderungsdatum. Die Quellensammlung kann noch ausstehen.",
    retry: "Aktualisieren",
    viewer:
      "Sie können gespeicherte Quellen prüfen und Interessen testen. Organisationsadministratoren aktivieren Pakete und speichern gemeinsame Monitoring-Themen.",
    existing:
      "Ein gleichwertiges Monitoring-Thema besteht bereits. Prüfen Sie es, bevor Sie ein weiteres erstellen.",
    manage: "Monitoring-Themen verwalten",
    notifications: "Benachrichtigungen wählen",
    back: "Zurück zum Einstieg",
  },
  "fr-CH": {
    dataset: "Jeu officiel et attribution",
    matched: "Termes correspondants",
    separate: "Pilote cantonal · activation distincte du pack fédéral",
    title: "Commencer avec Bâle-Ville",
    intro:
      "Choisissez un intérêt, consultez un acte enregistré correspondant et décidez quoi suivre. Ces étapes ne nécessitent pas d’IA.",
    open: "Ouvrir le guide de Bâle-Ville",
    sources: "1. Vérifier et activer le pack de sources",
    enable: "Activer Bâle-Ville pour cette organisation",
    collect: "Collecter les deux actes de départ",
    queued:
      "La collecte a été demandée récemment ou est en attente. Actualisez bientôt l’aperçu; le traitement en arrière-plan et la source officielle doivent être disponibles.",
    interest: "2. Décrire votre intérêt",
    name: "Nom de l’intérêt",
    terms: "Concepts allemands séparés par des virgules",
    exclusions: "Concepts exclus séparés par des virgules",
    termsHelp:
      "Les textes sources sont allemands. Modifiez les termes proposés; la correspondance repose sur les termes et métadonnées, sans interprétation juridique.",
    privacy: "Protection des données",
    building: "Construction et aménagement",
    preview: "Voir les correspondances enregistrées",
    save: "Enregistrer ce sujet de suivi pour l’organisation",
    saved:
      "Sujet enregistré. Ouvrez la preuve ci-dessous; choisissez les notifications séparément.",
    evidence: "Ouvrir la preuve enregistrée",
    source: "Version chez l’éditeur",
    empty:
      "Aucune correspondance dans l’échantillon enregistré examiné. Collectez les actes de départ, actualisez ou affinez les termes. Cela ne signifie pas qu’aucun acte pertinent n’existe.",
    scope:
      "Cet aperçu examine au maximum 500 événements enregistrés et affiche 10 correspondances. La détection n’est pas une date de modification juridique. La collecte peut être en attente.",
    retry: "Actualiser",
    viewer:
      "Vous pouvez consulter les sources et tester des intérêts. Un administrateur active les packs et enregistre les sujets partagés.",
    existing:
      "Un sujet équivalent existe déjà. Consultez-le avant d’en créer un autre.",
    manage: "Gérer les sujets de suivi",
    notifications: "Choisir les notifications",
    back: "Retour au démarrage",
  },
  "it-CH": {
    dataset: "Dataset ufficiale e attribuzione",
    matched: "Termini corrispondenti",
    separate: "Pilota cantonale · attivazione separata dal pacchetto federale",
    title: "Iniziare con Basilea Città",
    intro:
      "Scegli un interesse, consulta un atto salvato corrispondente e decidi cosa monitorare. Questi passaggi non richiedono IA.",
    open: "Apri la guida di Basilea Città",
    sources: "1. Verifica e attiva il pacchetto di fonti",
    enable: "Attiva Basilea Città per questa organizzazione",
    collect: "Raccogli i due atti iniziali",
    queued:
      "La raccolta è stata richiesta recentemente o è in coda. Aggiorna a breve l’anteprima; servono un processo in background attivo e la fonte ufficiale disponibile.",
    interest: "2. Descrivi il tuo interesse",
    name: "Nome dell’interesse",
    terms: "Concetti tedeschi separati da virgole",
    exclusions: "Concetti esclusi separati da virgole",
    termsHelp:
      "I testi originali sono tedeschi. Modifica i termini proposti; le corrispondenze dipendono da termini e metadati, senza interpretazione giuridica.",
    privacy: "Protezione dei dati",
    building: "Edilizia e pianificazione",
    preview: "Mostra le corrispondenze salvate",
    save: "Salva questo tema di monitoraggio per l’organizzazione",
    saved:
      "Tema salvato. Apri la prova qui sotto; scegli le notifiche separatamente.",
    evidence: "Apri la prova salvata",
    source: "Versione dell’editore",
    empty:
      "Nessuna corrispondenza nel campione salvato esaminato. Raccogli gli atti iniziali, aggiorna o affina i concetti. Ciò non significa che non esista un atto pertinente.",
    scope:
      "L’anteprima esamina al massimo 500 eventi salvati e mostra 10 corrispondenze. Il rilevamento non è una data di modifica normativa. La raccolta può essere ancora in attesa.",
    retry: "Aggiorna",
    viewer:
      "Puoi consultare le fonti salvate e provare gli interessi. Un amministratore attiva i pacchetti e salva i temi condivisi.",
    existing:
      "Esiste già un tema equivalente. Consultalo prima di crearne un altro.",
    manage: "Gestisci i temi",
    notifications: "Scegli le notifiche",
    back: "Torna alla guida iniziale",
  },
  "rm-CH": {
    dataset: "Dataset uffizial ed attribuziun",
    matched: "Noziuns correspundentas",
    separate: "Pilot chantunal · activaziun separada dal pachet federal",
    title: "Cumenzar cun Basilea-Citad",
    intro:
      "Tscherna in interess, examinescha in relasch memorisà adattà e decida tge survegliar. Quests pass na dovran nagina IA.",
    open: "Avrir il mussavia da Basilea-Citad",
    sources: "1. Examinar ed activar il pachet da funtaunas",
    enable: "Activar Basilea-Citad per questa organisaziun",
    collect: "Rimnar ils dus relaschs da partenza",
    queued:
      "La rimnada è vegnida dumandada dacurt u spetga en la colonna. Actualisescha la prevista prest; il process en il fund e la funtauna uffiziala ston esser disponibels.",
    interest: "2. Descriver tes interess",
    name: "Num da l’interess",
    terms: "Noziuns tudestgas separadas cun commas",
    exclusions: "Noziuns exclusas separadas cun commas",
    termsHelp:
      "Ils texts originals èn tudestgs. Adatta las noziuns proponidas; ils resultats sa basan sin noziuns e metadatas, betg sin in’interpretaziun giuridica.",
    privacy: "Protecziun da datas",
    building: "Construcziun e planisaziun",
    preview: "Examinar ils resultats memorisads",
    save: "Memorisar quest tema per l’organisaziun",
    saved:
      "Tema memorisà. Avra la cumprova qua sut; tscherna las notificaziuns separadamain.",
    evidence: "Avrir la cumprova memorisada",
    source: "Versiun da l’editur",
    empty:
      "Nagin resultat en l’emprova memorisada examinada. Rimna ils relaschs da partenza, actualisescha u adatta las noziuns. Quai na signifitga betg ch’i na dettia nagin relasch relevant.",
    scope:
      "La prevista examinescha maximalmain 500 eveniments memorisads e mussa 10 resultats. La detecziun n’è betg ina data da midada dal dretg. La rimnada po anc esser pendenta.",
    retry: "Actualisar",
    viewer:
      "Ti pos examinar funtaunas memorisadas e testar interess. In administratur activescha pachets e memorisescha temas communabels.",
    existing:
      "In tema equivalent exista gia. Examinescha quel avant da crear in auter.",
    manage: "Administrar ils temas",
    notifications: "Tscherner las notificaziuns",
    back: "Enavos al cumenzament",
  },
};
