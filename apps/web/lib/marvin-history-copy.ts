import type { Locale } from "./i18n";

const en = {
  title: "My Marvin conversations",
  intro:
    "Your private conversations in this organization. Viewing this history does not contact the AI or create a conversation.",
  retention:
    "For each context, the latest 40 messages, 20 Ask handoffs and one draft are saved until you delete the conversation. Older messages and handoffs are replaced as you continue.",
  limits:
    "Deleting here removes the personal conversation, not shared Ask/Impact answers, saved monitoring proposals, documents or monitors. Existing logs and backups are not erased by this action. Copies in another browser may remain until refreshed.",
  short:
    "This chat is personal. See saved messages, retention and deletion options in My Marvin conversations. Cited Ask answers are shared with your organization.",
  empty:
    "No saved conversations. When you use Marvin, your private history will appear here.",
  view: "Read conversation",
  remove: "Delete conversation",
  confirm: "Delete this private conversation?",
  deleted:
    "Private conversation deleted. Shared organization records were kept.",
  updated: "Last activity",
  created: "Created",
  draft: "Saved Ask draft",
  messages: "Messages",
  handoffs: "Questions handed to cited Ask",
  context: "Saved context",
  previous: "Newer conversations",
  next: "Older conversations",
  refresh: "Refresh history",
  back: "Back to conversations",
  loading: "Loading private history…",
  error:
    "Could not load this history. Retry or refresh the list. The conversation may have been deleted in another tab.",
  retry: "Retry",
  noContent: "This context has no saved messages or draft yet.",
  privacy: "Private history and retention",
};

export const marvinHistoryCopy: Record<Locale, typeof en> = {
  "en-CH": en,
  "de-CH": {
    title: "Meine Marvin-Gespräche",
    intro:
      "Ihre privaten Gespräche in dieser Organisation. Beim Lesen werden weder KI-Anfragen gesendet noch Gespräche erstellt.",
    retention:
      "Pro Kontext bleiben die letzten 40 Nachrichten, 20 Übergaben an Ask und ein Entwurf gespeichert, bis Sie das Gespräch löschen. Ältere Nachrichten und Übergaben werden beim Weiterschreiben ersetzt.",
    limits:
      "Hier löschen Sie das persönliche Gespräch, nicht die gemeinsamen Ask-/Impact-Antworten, gespeicherte Monitoring-Vorschläge, Dokumente oder Überwachungen. Bestehende Protokolle und Sicherungen werden nicht gelöscht. Kopien in einem anderen Browser können bis zur Aktualisierung bestehen bleiben.",
    short:
      "Dieser Chat ist persönlich. Gespeicherte Nachrichten, Aufbewahrung und Löschoptionen finden Sie unter «Meine Marvin-Gespräche». Belegte Ask-Antworten werden mit Ihrer Organisation geteilt.",
    empty:
      "Noch keine gespeicherten Gespräche. Wenn Sie Marvin nutzen, erscheint hier Ihr privater Verlauf.",
    view: "Gespräch lesen",
    remove: "Gespräch löschen",
    confirm: "Dieses private Gespräch löschen?",
    deleted:
      "Privates Gespräch gelöscht. Gemeinsame Organisationsdaten bleiben erhalten.",
    updated: "Letzte Aktivität",
    created: "Erstellt",
    draft: "Gespeicherter Ask-Entwurf",
    messages: "Nachrichten",
    handoffs: "An belegtes Ask übergebene Fragen",
    context: "Gespeicherter Kontext",
    previous: "Neuere Gespräche",
    next: "Ältere Gespräche",
    refresh: "Verlauf aktualisieren",
    back: "Zurück zu den Gesprächen",
    loading: "Privater Verlauf wird geladen…",
    error:
      "Dieser Verlauf konnte nicht geladen werden. Wiederholen Sie den Vorgang oder aktualisieren Sie die Liste. Das Gespräch wurde möglicherweise in einem anderen Tab gelöscht.",
    retry: "Erneut versuchen",
    noContent:
      "Für diesen Kontext sind noch keine Nachrichten oder Entwürfe gespeichert.",
    privacy: "Privater Verlauf und Aufbewahrung",
  },
  "fr-CH": {
    title: "Mes conversations avec Marvin",
    intro:
      "Vos conversations privées dans cette organisation. La consultation ne contacte pas l’IA et ne crée aucune conversation.",
    retention:
      "Pour chaque contexte, les 40 derniers messages, 20 transferts vers Ask et un brouillon sont conservés jusqu’à la suppression de la conversation. Les anciens messages et transferts sont remplacés au fil des échanges.",
    limits:
      "La suppression concerne la conversation personnelle, pas les réponses Ask/Impact partagées, les propositions de suivi enregistrées, les documents ni les suivis. Les journaux et sauvegardes existants ne sont pas effacés. Des copies dans un autre navigateur peuvent subsister jusqu’à son actualisation.",
    short:
      "Ce chat est personnel. Retrouvez les messages, la conservation et les options de suppression dans « Mes conversations avec Marvin ». Les réponses Ask sourcées sont partagées avec votre organisation.",
    empty:
      "Aucune conversation enregistrée. Votre historique privé apparaîtra ici lorsque vous utiliserez Marvin.",
    view: "Lire la conversation",
    remove: "Supprimer la conversation",
    confirm: "Supprimer cette conversation privée ?",
    deleted:
      "Conversation privée supprimée. Les données partagées de l’organisation ont été conservées.",
    updated: "Dernière activité",
    created: "Création",
    draft: "Brouillon Ask enregistré",
    messages: "Messages",
    handoffs: "Questions transmises à Ask avec sources",
    context: "Contexte enregistré",
    previous: "Conversations plus récentes",
    next: "Conversations plus anciennes",
    refresh: "Actualiser l’historique",
    back: "Retour aux conversations",
    loading: "Chargement de l’historique privé…",
    error:
      "Impossible de charger cet historique. Réessayez ou actualisez la liste. La conversation a peut-être été supprimée dans un autre onglet.",
    retry: "Réessayer",
    noContent:
      "Ce contexte ne contient pas encore de message ni de brouillon enregistré.",
    privacy: "Historique privé et conservation",
  },
  "it-CH": {
    title: "Le mie conversazioni con Marvin",
    intro:
      "Le tue conversazioni private in questa organizzazione. Consultarle non contatta l’IA e non crea conversazioni.",
    retention:
      "Per ogni contesto vengono conservati gli ultimi 40 messaggi, 20 passaggi ad Ask e una bozza, finché non elimini la conversazione. I messaggi e i passaggi più vecchi vengono sostituiti quando continui.",
    limits:
      "L’eliminazione riguarda la conversazione personale, non le risposte Ask/Impact condivise, le proposte di monitoraggio salvate, i documenti o i monitoraggi. I log e i backup esistenti non vengono cancellati. Copie in un altro browser possono rimanere fino all’aggiornamento.",
    short:
      "Questa chat è personale. Messaggi, conservazione e opzioni di eliminazione sono in «Le mie conversazioni con Marvin». Le risposte Ask con fonti sono condivise con la tua organizzazione.",
    empty:
      "Nessuna conversazione salvata. Quando usi Marvin, la tua cronologia privata apparirà qui.",
    view: "Leggi conversazione",
    remove: "Elimina conversazione",
    confirm: "Eliminare questa conversazione privata?",
    deleted:
      "Conversazione privata eliminata. I dati condivisi dell’organizzazione sono stati conservati.",
    updated: "Ultima attività",
    created: "Creazione",
    draft: "Bozza Ask salvata",
    messages: "Messaggi",
    handoffs: "Domande passate ad Ask con fonti",
    context: "Contesto salvato",
    previous: "Conversazioni più recenti",
    next: "Conversazioni meno recenti",
    refresh: "Aggiorna cronologia",
    back: "Torna alle conversazioni",
    loading: "Caricamento della cronologia privata…",
    error:
      "Impossibile caricare questa cronologia. Riprova o aggiorna l’elenco. La conversazione potrebbe essere stata eliminata in un’altra scheda.",
    retry: "Riprova",
    noContent: "Questo contesto non ha ancora messaggi o bozze salvati.",
    privacy: "Cronologia privata e conservazione",
  },
  "rm-CH": {
    title: "Mes discurs cun Marvin",
    intro:
      "Voss discurs privats en questa organisaziun. La lectura na contactescha betg l’IA e na creescha nagin discurs.",
    retention:
      "Per mintga context vegnan conservads ils ultims 40 messadis, 20 surdadas ad Ask ed in sboz fin che Vus stizzais il discurs. Messadis e surdadas pli vegls vegnan remplazzads cun cuntinuar.",
    limits:
      "Qua stizzais Vus il discurs persunal, betg las respostas Ask/Impact communablas, las propostas da surveglianza memorisadas, ils documents u las surveglianzas. Protocolls e copias da segirezza existents na vegnan betg stizzads. Copias en in auter navigatur pon restar fin a l’actualisaziun.",
    short:
      "Quest chat è persunal. Messadis, conservaziun ed opziuns da stizzar èn sut «Mes discurs cun Marvin». Respostas Ask cun funtaunas vegnan partìdas cun Vossa organisaziun.",
    empty:
      "Anc nagins discurs memorisads. Cura che Vus utilisais Marvin, cumpara qua Vossa cronologia privata.",
    view: "Leger il discurs",
    remove: "Stizzar il discurs",
    confirm: "Stizzar quest discurs privat?",
    deleted:
      "Discurs privat stizzà. Las datas communablas da l’organisaziun èn restadas.",
    updated: "Ultima activitad",
    created: "Creà",
    draft: "Sboz Ask memorisà",
    messages: "Messadis",
    handoffs: "Dumondas surdadas ad Ask cun funtaunas",
    context: "Context memorisà",
    previous: "Discurs pli novs",
    next: "Discurs pli vegls",
    refresh: "Actualisar la cronologia",
    back: "Enavos tar ils discurs",
    loading: "Chargiar la cronologia privata…",
    error:
      "Impussibel da chargiar questa cronologia. Empruvai anc ina giada u actualisai la glista. Il discurs è eventualmain vegnì stizzà en in auter tab.",
    retry: "Empruvar anc ina giada",
    noContent: "Quest context n’ha anc nagins messadis u sbozs memorisads.",
    privacy: "Cronologia privata e conservaziun",
  },
};
