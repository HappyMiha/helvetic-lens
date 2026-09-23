import type { Locale } from "./i18n";
const en = {
  title: "Saved cloud connections",
  intro:
    "Keep OpenAI and Swisscom credentials separately. Save and test each connection, then activate the one that should handle this organization's analyses. Saving changes here does not update the active settings.",
  saved: "Connection saved. Activate it to use these settings.",
  activate: "Use for this organization",
  removeKey: "Remove saved key",
  activated: "This connection is now active for the organization.",
  tested:
    "The provider answered the technical check. Legal answer quality was not evaluated.",
  access: "Get participant access",
  openai:
    "The $50 offer is a billing credit. Redeem it in the intended OpenAI organization, then create an API key and choose an available model. OpenAI uses its model's default sampling settings.",
  swisscom:
    "Swiss {ai} Weeks: Apertus 1.5 70B. The organizer states that bearer authorization expires after 60 minutes. Check the issued credential instructions; an expired credential needs renewal.",
};
export const cloudConnectionsCopy: Record<Locale, typeof en> = {
  "en-CH": en,
  "de-CH": {
    title: "Gespeicherte Cloud-Verbindungen",
    intro:
      "OpenAI- und Swisscom-Zugangsdaten getrennt speichern und testen. Aktivieren Sie danach die Verbindung für die Analysen dieser Organisation. Änderungen hier aktualisieren die aktiven Einstellungen nicht.",
    saved:
      "Verbindung gespeichert. Aktivieren Sie sie, um diese Einstellungen zu nutzen.",
    activate: "Für diese Organisation verwenden",
    removeKey: "Gespeicherten Schlüssel entfernen",
    activated: "Diese Verbindung ist jetzt für die Organisation aktiv.",
    tested:
      "Der Anbieter hat die technische Prüfung beantwortet. Die Qualität juristischer Antworten wurde nicht bewertet.",
    access: "Teilnehmerzugang erhalten",
    openai:
      "Das Angebot über USD 50 ist ein Rechnungsguthaben. Lösen Sie es in der gewünschten OpenAI-Organisation ein, erstellen Sie einen API-Schlüssel und wählen Sie ein verfügbares Modell. OpenAI verwendet die Sampling-Standardwerte des Modells.",
    swisscom:
      "Swiss {ai} Weeks: Apertus 1.5 70B. Laut Veranstalter läuft die Bearer-Autorisierung nach 60 Minuten ab. Beachten Sie die Anweisungen zu Ihren Zugangsdaten; abgelaufene Zugangsdaten müssen erneuert werden.",
  },
  "fr-CH": {
    title: "Connexions cloud enregistrées",
    intro:
      "Enregistrez et testez séparément les accès OpenAI et Swisscom, puis activez la connexion destinée aux analyses de cette organisation. Les modifications ici ne changent pas les paramètres actifs.",
    saved: "Connexion enregistrée. Activez-la pour utiliser ces paramètres.",
    activate: "Utiliser pour cette organisation",
    removeKey: "Supprimer la clé enregistrée",
    activated: "Cette connexion est maintenant active pour l’organisation.",
    tested:
      "Le fournisseur a répondu au contrôle technique. La qualité juridique des réponses n’a pas été évaluée.",
    access: "Obtenir l’accès participant",
    openai:
      "L’offre de 50 USD est un crédit de facturation. Activez-le dans l’organisation OpenAI souhaitée, puis créez une clé API et choisissez un modèle disponible. OpenAI utilise les paramètres d’échantillonnage par défaut du modèle.",
    swisscom:
      "Swiss {ai} Weeks : Apertus 1.5 70B. L’organisateur annonce une expiration de l’autorisation Bearer après 60 minutes. Consultez les instructions reçues ; un accès expiré doit être renouvelé.",
  },
  "it-CH": {
    title: "Connessioni cloud salvate",
    intro:
      "Salva e verifica separatamente le credenziali OpenAI e Swisscom, poi attiva la connessione per le analisi di questa organizzazione. Le modifiche qui non aggiornano le impostazioni attive.",
    saved: "Connessione salvata. Attivala per utilizzare queste impostazioni.",
    activate: "Usa per questa organizzazione",
    removeKey: "Rimuovi la chiave salvata",
    activated: "Questa connessione è ora attiva per l’organizzazione.",
    tested:
      "Il fornitore ha risposto alla verifica tecnica. La qualità delle risposte giuridiche non è stata valutata.",
    access: "Ottieni l’accesso partecipante",
    openai:
      "L’offerta di 50 USD è un credito di fatturazione. Riscattalo nell’organizzazione OpenAI desiderata, poi crea una chiave API e scegli un modello disponibile. OpenAI usa i parametri di campionamento predefiniti del modello.",
    swisscom:
      "Swiss {ai} Weeks: Apertus 1.5 70B. L’organizzatore indica che l’autorizzazione Bearer scade dopo 60 minuti. Consulta le istruzioni ricevute; una credenziale scaduta richiede il rinnovo.",
  },
  "rm-CH": {
    title: "Colliaziuns cloud memorisadas",
    intro:
      "Memorisar e testar separadamain las datas d’access dad OpenAI e Swisscom. Activai alura la colliaziun per las analisas da questa organisaziun. Midadas qua na midan betg las configuraziuns activas.",
    saved:
      "Colliaziun memorisada. Activai ella per duvrar questas configuraziuns.",
    activate: "Duvrar per questa organisaziun",
    removeKey: "Allontanar la clav memorisada",
    activated: "Questa colliaziun è ussa activa per l’organisaziun.",
    tested:
      "Il purschider ha respundì al test tecnic. La qualitad da las respostas giuridicas n’è betg vegnida valitada.",
    access: "Obtegnair access per participants",
    openai:
      "L’offerta da 50 USD è in credit da quint. Activai el en l’organisaziun OpenAI giavischada, creai ina clav API e tschernì in model disponibel. OpenAI dovra las valurs da sampling standard dal model.",
    swisscom:
      "Swiss {ai} Weeks: Apertus 1.5 70B. Tenor l’organisatur scada l’autorisaziun Bearer suenter 60 minutas. Consultai las instrucziuns retschavidas; datas d’access scadidas ston vegnir renovadas.",
  },
};
