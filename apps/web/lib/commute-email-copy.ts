import type { Locale } from "./i18n";

const en = {
  consent:
    "I agree to receive Commute Watch emails at my verified account address.",
  active: "Email consent is active.",
  off: "Email consent is inactive.",
  verify: "Verify your account email before enabling delivery.",
  note: "Only new journey changes after your consent are considered. Turning email on does not resend history. Opening a message does not mark an update reviewed.",
  window:
    "Email considers the latest unreviewed updates from the last 48 hours. A daily digest sends at most once per local day. Outside-window updates require both the journey's digest setting and daily email consent.",
  serviceOff:
    "The sending service is unavailable. You can save preferences; delivery requires an available service, permitted sources and an active journey.",
  uncertain:
    "A previous email attempt has an uncertain outcome and will not be repeated automatically. Check your mailbox before asking the operator to investigate.",
  preview: "Preview currently due email items",
  previewNote:
    "This preview uses your saved settings. It does not send an email.",
  none: "No eligible email items are currently due.",
  unavailable:
    "Delivery is unavailable under the current consent, source or journey state.",
  daily:
    "Today's daily email has already been attempted. Further eligible updates wait for the next scheduled delivery.",
  quiet: "Quiet hours are active. These items will wait.",
  more: "The preview shows at most 50 items. Further updates may remain; review the journey's events.",
  save: "Save email settings",
};

export const commuteEmailCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    consent:
      "Ich stimme Commute-Watch-E-Mails an meine bestätigte Kontoadresse zu.",
    active: "Die E-Mail-Zustimmung ist aktiv.",
    off: "Die E-Mail-Zustimmung ist inaktiv.",
    verify:
      "Bestätigen Sie Ihre Konto-E-Mail, bevor Sie den Versand aktivieren.",
    note: "Berücksichtigt werden nur neue Fahrtänderungen nach Ihrer Zustimmung. Das Einschalten versendet keine alte Historie. Das Öffnen einer Nachricht markiert keine Änderung als geprüft.",
    window:
      "E-Mails berücksichtigen die neuesten ungeprüften Änderungen der letzten 48 Stunden. Eine tägliche Zusammenfassung wird höchstens einmal pro lokalem Tag gesendet. Ausserhalb des Zeitfensters braucht es die Zusammenfassungsoption der Fahrt und die Zustimmung zur täglichen E-Mail.",
    serviceOff:
      "Der Versanddienst ist nicht verfügbar. Sie können Einstellungen speichern; der Versand erfordert einen verfügbaren Dienst, erlaubte Quellen und eine aktive Fahrt.",
    uncertain:
      "Der Ausgang eines früheren E-Mail-Versuchs ist ungewiss. Er wird nicht automatisch wiederholt. Prüfen Sie Ihr Postfach, bevor Sie den Betreiber um Prüfung bitten.",
    preview: "Aktuell fällige E-Mail-Einträge ansehen",
    previewNote:
      "Die Vorschau verwendet Ihre gespeicherten Einstellungen. Sie sendet keine E-Mail.",
    none: "Derzeit sind keine geeigneten E-Mail-Einträge fällig.",
    unavailable:
      "Der Versand ist mit der aktuellen Zustimmung, Quelle oder dem Fahrtstatus nicht verfügbar.",
    daily:
      "Der tägliche Versand wurde heute bereits versucht. Weitere geeignete Änderungen warten auf den nächsten geplanten Versand.",
    quiet: "Ruhezeiten sind aktiv. Diese Einträge warten.",
    more: "Die Vorschau zeigt höchstens 50 Einträge. Weitere Änderungen können ausstehen; prüfen Sie die Ereignisse der Fahrt.",
    save: "E-Mail-Einstellungen speichern",
  },
  "fr-CH": {
    consent:
      "J’accepte de recevoir les e-mails Commute Watch à l’adresse vérifiée de mon compte.",
    active: "Le consentement aux e-mails est actif.",
    off: "Le consentement aux e-mails est inactif.",
    verify: "Vérifiez l’adresse de votre compte avant d’activer l’envoi.",
    note: "Seuls les nouveaux changements de trajet après votre consentement sont considérés. L’activation ne renvoie pas l’historique. Ouvrir un message ne marque pas une mise à jour comme examinée.",
    window:
      "Les e-mails considèrent les dernières mises à jour non examinées des 48 dernières heures. Un résumé quotidien est envoyé au plus une fois par jour local. Les changements hors créneau nécessitent l’option résumé du trajet et le consentement aux e-mails quotidiens.",
    serviceOff:
      "Le service d’envoi est indisponible. Vous pouvez enregistrer vos préférences ; l’envoi nécessite un service disponible, des sources autorisées et un trajet actif.",
    uncertain:
      "Le résultat d’une tentative d’envoi précédente est incertain. Elle ne sera pas répétée automatiquement. Vérifiez votre boîte avant de demander une enquête à l’exploitant.",
    preview: "Aperçu des éléments e-mail actuellement dus",
    previewNote:
      "L’aperçu utilise vos préférences enregistrées. Il n’envoie aucun e-mail.",
    none: "Aucun élément admissible n’est actuellement dû.",
    unavailable:
      "L’envoi est indisponible avec le consentement, la source ou l’état du trajet actuels.",
    daily:
      "L’envoi quotidien a déjà été tenté aujourd’hui. Les autres mises à jour admissibles attendent le prochain envoi prévu.",
    quiet: "La période de silence est active. Ces éléments attendront.",
    more: "L’aperçu montre au plus 50 éléments. D’autres peuvent rester ; consultez les événements du trajet.",
    save: "Enregistrer les préférences e-mail",
  },
  "it-CH": {
    consent:
      "Acconsento a ricevere le e-mail Commute Watch all’indirizzo verificato del mio account.",
    active: "Il consenso alle e-mail è attivo.",
    off: "Il consenso alle e-mail è inattivo.",
    verify: "Verifica l’e-mail del tuo account prima di attivare l’invio.",
    note: "Sono considerate solo le nuove modifiche al viaggio dopo il consenso. L’attivazione non invia nuovamente la cronologia. Aprire un messaggio non contrassegna un aggiornamento come esaminato.",
    window:
      "Le e-mail considerano gli ultimi aggiornamenti non esaminati delle ultime 48 ore. Un riepilogo giornaliero viene inviato al massimo una volta per giorno locale. Gli aggiornamenti fuori fascia richiedono l’opzione riepilogo del viaggio e il consenso alle e-mail giornaliere.",
    serviceOff:
      "Il servizio di invio non è disponibile. Puoi salvare le preferenze; l’invio richiede un servizio disponibile, fonti autorizzate e un viaggio attivo.",
    uncertain:
      "L’esito di un precedente tentativo di invio è incerto e non verrà ripetuto automaticamente. Controlla la casella prima di chiedere una verifica al gestore.",
    preview: "Anteprima degli elementi e-mail da inviare",
    previewNote:
      "L’anteprima usa le preferenze salvate. Non invia alcuna e-mail.",
    none: "Nessun elemento idoneo è attualmente da inviare.",
    unavailable:
      "L’invio non è disponibile con il consenso, la fonte o lo stato del viaggio attuali.",
    daily:
      "L’invio giornaliero è già stato tentato oggi. Gli altri aggiornamenti idonei attendono il prossimo invio previsto.",
    quiet: "Le ore di silenzio sono attive. Questi elementi attenderanno.",
    more: "L’anteprima mostra al massimo 50 elementi. Altri possono rimanere; consulta gli eventi del viaggio.",
    save: "Salva preferenze e-mail",
  },
  "rm-CH": {
    consent:
      "Jau accept da retschaiver e-mails Commute Watch a l’adressa verifitgada da mes conto.",
    active: "Il consentiment per e-mails è activ.",
    off: "Il consentiment per e-mails è inactiv.",
    verify: "Verifitgai l’adressa da vos conto avant d’activar la spediziun.",
    note: "Resguardadas vegnan mo novas midadas dal viadi suenter il consentiment. L’activaziun na trametta betg l’istorgia veglia. Avrir in messadi na marchescha betg ina midada sco controllada.",
    window:
      "Ils e-mails resguardan las ultimas midadas betg controlladas da las ultimas 48 uras. Ina resumaziun vegn tramessa maximalmain ina giada per di local. Midadas ordaifer la fanestra dovran l’opziun da resumaziun dal viadi ed il consentiment per e-mails quotidians.",
    serviceOff:
      "Il servetsch da spediziun n’è betg disponibel. Vus pudais memorisar preferenzas; la spediziun dovra in servetsch disponibel, funtaunas permessas ed in viadi activ.",
    uncertain:
      "Il resultat d’ina tentativa anteriura d’e-mail è malsegir e na vegn betg repetì automaticamain. Controllai la chascha postala avant da dumandar ina controlla al gestiunari.",
    preview: "Prevista dals elements pronts per e-mail",
    previewNote:
      "La prevista dovra las preferenzas memorisadas. Ella na trametta nagin e-mail.",
    none: "Actualmain n’èn nagins elements adattads pronts.",
    unavailable:
      "La spediziun n’è betg disponibla cun il consentiment, la funtauna u il stadi dal viadi actual.",
    daily:
      "La spediziun quotidiana è gia vegnida empruvada oz. Ulteriuras midadas adattadas spetgan la proxima spediziun planisada.",
    quiet: "Las uras da ruaus èn activas. Quests elements spetgan.",
    more: "La prevista mussa maximalmain 50 elements. Ulteriurs pon restar; controllai ils eveniments dal viadi.",
    save: "Memorisar preferenzas dad e-mail",
  },
};
