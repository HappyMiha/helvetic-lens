import type { Locale } from "./i18n";

const en = {
  uncertain:
    "A previous email attempt has an uncertain outcome. It will not be resent automatically; check your mailbox before asking the operator to investigate.",
  serviceOff:
    "The email sending service is unavailable. You can save preferences; no email will be sent while it is unavailable.",
  consent:
    "I agree to receive these Tender Watch emails at my verified account address.",
  active: "Email consent is active.",
  off: "Email is turned off.",
  verify: "Verify your account email before enabling delivery.",
  note: "Only new discoveries and changes to followed tenders are considered. Turning email on does not resend old history. Messages link to private evidence; no bid is submitted.",
  preview: "Preview currently due email items",
  none: "No eligible email items are currently due.",
  unavailable:
    "Delivery is unavailable under the current consent, source or daily schedule.",
  quiet: "Quiet hours are active. These items will wait.",
  more: "This preview is limited to 50 items. Additional items may remain; review all tenders in the monitor.",
  window:
    "Email considers the latest unreviewed evidence from the last 48 hours. A daily digest sends at most once per local day; late or unavailable data can leave gaps.",
  older:
    "This link refers to an earlier evidence version. The current tender is shown below; open the linked original to inspect the earlier publication.",
};

export const tenderEmailCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    uncertain:
      "Der Ausgang eines früheren E-Mail-Versuchs ist ungewiss. Er wird nicht automatisch wiederholt. Prüfen Sie Ihr Postfach, bevor Sie den Betreiber um Prüfung bitten.",
    serviceOff:
      "Der E-Mail-Dienst ist nicht verfügbar. Sie können Einstellungen speichern; währenddessen werden keine E-Mails gesendet.",
    consent:
      "Ich stimme diesen Tender-Watch-E-Mails an meine bestätigte Kontoadresse zu.",
    active: "Die E-Mail-Zustimmung ist aktiv.",
    off: "E-Mail ist ausgeschaltet.",
    verify:
      "Bestätigen Sie Ihre Konto-E-Mail, bevor Sie den Versand aktivieren.",
    note: "Berücksichtigt werden neue Funde und Änderungen an verfolgten Ausschreibungen. Das Einschalten versendet keine alte Historie. Nachrichten verlinken private Belege; es wird kein Angebot eingereicht.",
    preview: "Aktuell fällige E-Mail-Einträge ansehen",
    none: "Derzeit sind keine geeigneten E-Mail-Einträge fällig.",
    unavailable:
      "Der Versand ist mit der aktuellen Zustimmung, Quelle oder Tagesplanung nicht verfügbar.",
    quiet: "Ruhezeiten sind aktiv. Diese Einträge warten.",
    more: "Die Vorschau zeigt höchstens 50 Einträge. Weitere können ausstehen; prüfen Sie alle Ausschreibungen im Monitor.",
    window:
      "E-Mails berücksichtigen die neuesten ungeprüften Belege der letzten 48 Stunden. Eine tägliche Zusammenfassung wird höchstens einmal pro lokalem Tag gesendet; verspätete oder fehlende Daten können Lücken verursachen.",
    older:
      "Dieser Link verweist auf eine frühere Belegversion. Unten steht die aktuelle Ausschreibung. Öffnen Sie das verlinkte Original für die frühere Publikation.",
  },
  "fr-CH": {
    uncertain:
      "Le résultat d’une tentative d’envoi précédente est incertain. Elle ne sera pas répétée automatiquement ; vérifiez votre boîte avant de demander une enquête à l’exploitant.",
    serviceOff:
      "Le service d’envoi est indisponible. Vous pouvez enregistrer vos préférences ; aucun e-mail ne sera envoyé pendant cette indisponibilité.",
    consent:
      "J’accepte de recevoir ces e-mails Tender Watch à l’adresse vérifiée de mon compte.",
    active: "Le consentement aux e-mails est actif.",
    off: "Les e-mails sont désactivés.",
    verify: "Vérifiez l’adresse de votre compte avant d’activer l’envoi.",
    note: "Seules les nouvelles découvertes et les modifications des appels d’offres suivis sont considérées. L’activation ne renvoie pas l’ancien historique. Les messages renvoient aux preuves privées ; aucune offre n’est soumise.",
    preview: "Aperçu des éléments actuellement dus par e-mail",
    none: "Aucun élément admissible n’est actuellement dû.",
    unavailable:
      "L’envoi est indisponible avec le consentement, la source ou le calendrier quotidien actuels.",
    quiet: "La période de silence est active. Ces éléments attendront.",
    more: "L’aperçu est limité à 50 éléments. D’autres peuvent rester en attente ; consultez tous les appels d’offres du suivi.",
    window:
      "Les e-mails considèrent les dernières preuves non examinées des 48 dernières heures. Un résumé quotidien est envoyé au plus une fois par jour local ; des données tardives ou indisponibles peuvent laisser des lacunes.",
    older:
      "Ce lien désigne une version antérieure des preuves. L’appel d’offres actuel est affiché ci-dessous ; ouvrez l’original lié pour consulter l’ancienne publication.",
  },
  "it-CH": {
    uncertain:
      "L’esito di un precedente tentativo di invio è incerto. Non verrà ripetuto automaticamente; controlla la casella prima di chiedere una verifica al gestore.",
    serviceOff:
      "Il servizio di invio e-mail non è disponibile. Puoi salvare le preferenze; nessuna e-mail sarà inviata durante l’indisponibilità.",
    consent:
      "Acconsento a ricevere queste e-mail Tender Watch all’indirizzo verificato del mio account.",
    active: "Il consenso alle e-mail è attivo.",
    off: "Le e-mail sono disattivate.",
    verify: "Verifica l’e-mail del tuo account prima di attivare l’invio.",
    note: "Sono considerate solo le nuove opportunità e le modifiche dei bandi seguiti. L’attivazione non invia nuovamente la cronologia. I messaggi rimandano alle prove private; non viene presentata alcuna offerta.",
    preview: "Anteprima degli elementi e-mail attualmente in scadenza",
    none: "Nessun elemento idoneo è attualmente da inviare.",
    unavailable:
      "L’invio non è disponibile con il consenso, la fonte o la pianificazione giornaliera attuali.",
    quiet: "Le ore di silenzio sono attive. Questi elementi attenderanno.",
    more: "L’anteprima è limitata a 50 elementi. Altri possono essere in attesa; consulta tutti i bandi nel monitoraggio.",
    window:
      "Le e-mail considerano le prove più recenti non esaminate delle ultime 48 ore. Un riepilogo giornaliero è inviato al massimo una volta per giorno locale; dati tardivi o non disponibili possono lasciare lacune.",
    older:
      "Questo link si riferisce a una versione precedente delle prove. Sotto è mostrato il bando attuale; apri l’originale collegato per esaminare la pubblicazione precedente.",
  },
  "rm-CH": {
    uncertain:
      "Il resultat d’ina tentativa anteriura d’e-mail è malsegir. Ella na vegn betg repetida automaticamain; controllai la chascha postala avant da dumandar ina controlla al gestiunari.",
    serviceOff:
      "Il servetsch da spediziun dad e-mails n’è betg disponibel. Vus pudais memorisar preferenzas; nagins e-mails na vegnan tramess durant l’indisponibladad.",
    consent:
      "Jau accept da retschaiver quests e-mails Tender Watch a l’adressa verifitgada da mes conto.",
    active: "Il consentiment per e-mails è activ.",
    off: "Ils e-mails èn deactivads.",
    verify: "Verifitgai l’adressa da vos conto avant d’activar la spediziun.",
    note: "Resguardads vegnan novas occasiuns e midadas da las publicaziuns suandadas. L’activaziun na trametta betg l’istorgia veglia. Ils messadis collian cumprovas privatas; nagina offerta na vegn inoltrada.",
    preview: "Prevista dals elements actualmain pronts per e-mail",
    none: "Actualmain n’èn nagins elements adattads pronts.",
    unavailable:
      "La spediziun n’è betg disponibla cun il consentiment, la funtauna u l’urari quotidian actual.",
    quiet: "Las uras da ruaus èn activas. Quests elements spetgan.",
    more: "La prevista è limitada a 50 elements. Ulteriurs pon spetgar; controllai tut las publicaziuns en il monitoring.",
    window:
      "Ils e-mails resguardan las cumprovas las pli novas betg controlladas da las ultimas 48 uras. Ina resumaziun quotidiana vegn tramessa maximalmain ina giada per di local; datas tardivas u mancantas pon laschar largias.",
    older:
      "Questa colliaziun sa referescha ad ina versiun anteriura da las cumprovas. Sutvart stat la publicaziun actuala; avri l’original collià per examinar la publicaziun anteriura.",
  },
};
