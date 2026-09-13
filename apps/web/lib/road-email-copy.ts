import type { Locale } from "./i18n";

const en = {
  consent:
    "I agree to receive Road Watch emails at my verified account address.",
  active: "Email consent is active.",
  off: "Email consent is inactive.",
  verify: "Verify your account email before enabling delivery.",
  note: "Only new route changes after your consent are considered. Turning email on does not resend history. Opening a message does not mark an update reviewed.",
  window:
    "Email considers current unreviewed changes from the last 48 hours. A daily digest sends at most once per local day. Source and corridor permissions are checked again before sending.",
  serviceOff:
    "The sending service is unavailable. You can save preferences; delivery requires an available service, permitted sources and an active route.",
  uncertain:
    "A previous email attempt has an uncertain outcome and will not be repeated automatically. Check your mailbox before asking the operator to investigate.",
  preview: "Preview currently due email items",
  previewNote:
    "This preview uses your saved settings. It does not send an email.",
  none: "No eligible email items are currently due.",
  unavailable:
    "Delivery is unavailable under the current consent, source or route state.",
  daily:
    "Today's daily email has already been attempted. Further eligible updates wait for the next scheduled delivery.",
  quiet: "Quiet hours are active. These items will wait.",
  more: "The preview shows at most 50 items. Further updates may remain; review the route's events.",
  save: "Save email settings",
};

export const roadEmailCopy: Record<Locale, Record<keyof typeof en, string>> = {
  "en-CH": en,
  "de-CH": {
    consent:
      "Ich stimme Road-Watch-E-Mails an meine bestätigte Kontoadresse zu.",
    active: "Die E-Mail-Zustimmung ist aktiv.",
    off: "Die E-Mail-Zustimmung ist inaktiv.",
    verify:
      "Bestätigen Sie Ihre Konto-E-Mail, bevor Sie den Versand aktivieren.",
    note: "Berücksichtigt werden nur neue Strassenänderungen nach Ihrer Zustimmung. Das Einschalten versendet keine alte Historie. Das Öffnen einer Nachricht markiert keine Änderung als geprüft.",
    window:
      "E-Mails berücksichtigen aktuelle ungeprüfte Änderungen der letzten 48 Stunden. Eine tägliche Zusammenfassung wird höchstens einmal pro lokalem Tag gesendet. Quellen- und Korridorberechtigungen werden vor dem Versand erneut geprüft.",
    serviceOff:
      "Der Versanddienst ist nicht verfügbar. Sie können Einstellungen speichern; der Versand erfordert einen verfügbaren Dienst, erlaubte Quellen und eine aktive Route.",
    uncertain:
      "Der Ausgang eines früheren E-Mail-Versuchs ist ungewiss. Er wird nicht automatisch wiederholt. Prüfen Sie Ihr Postfach, bevor Sie den Betreiber um Prüfung bitten.",
    preview: "Aktuell fällige E-Mail-Einträge ansehen",
    previewNote:
      "Die Vorschau verwendet Ihre gespeicherten Einstellungen. Sie sendet keine E-Mail.",
    none: "Derzeit sind keine geeigneten E-Mail-Einträge fällig.",
    unavailable:
      "Der Versand ist mit der aktuellen Zustimmung, Quelle oder dem Routenstatus nicht verfügbar.",
    daily:
      "Der tägliche Versand wurde heute bereits versucht. Weitere geeignete Änderungen warten auf den nächsten geplanten Versand.",
    quiet: "Ruhezeiten sind aktiv. Diese Einträge warten.",
    more: "Die Vorschau zeigt höchstens 50 Einträge. Weitere Änderungen können ausstehen; prüfen Sie die Ereignisse der Route.",
    save: "E-Mail-Einstellungen speichern",
  },
  "fr-CH": {
    consent:
      "J’accepte de recevoir les e-mails Road Watch à l’adresse vérifiée de mon compte.",
    active: "Le consentement aux e-mails est actif.",
    off: "Le consentement aux e-mails est inactif.",
    verify: "Vérifiez l’adresse de votre compte avant d’activer l’envoi.",
    note: "Seuls les nouveaux changements de itinéraire après votre consentement sont considérés. L’activation ne renvoie pas l’historique. Ouvrir un message ne marque pas une mise à jour comme examinée.",
    window:
      "Les e-mails considèrent les changements actuels non examinés des 48 dernières heures. Un résumé quotidien est envoyé au plus une fois par jour local. Les autorisations des sources et des corridors sont revérifiées avant l’envoi.",
    serviceOff:
      "Le service d’envoi est indisponible. Vous pouvez enregistrer vos préférences ; l’envoi nécessite un service disponible, des sources autorisées et un itinéraire actif.",
    uncertain:
      "Le résultat d’une tentative d’envoi précédente est incertain. Elle ne sera pas répétée automatiquement. Vérifiez votre boîte avant de demander une enquête à l’exploitant.",
    preview: "Aperçu des éléments e-mail actuellement dus",
    previewNote:
      "L’aperçu utilise vos préférences enregistrées. Il n’envoie aucun e-mail.",
    none: "Aucun élément admissible n’est actuellement dû.",
    unavailable:
      "L’envoi est indisponible avec le consentement, la source ou l’état du itinéraire actuels.",
    daily:
      "L’envoi quotidien a déjà été tenté aujourd’hui. Les autres mises à jour admissibles attendent le prochain envoi prévu.",
    quiet: "La période de silence est active. Ces éléments attendront.",
    more: "L’aperçu montre au plus 50 éléments. D’autres peuvent rester ; consultez les événements du itinéraire.",
    save: "Enregistrer les préférences e-mail",
  },
  "it-CH": {
    consent:
      "Acconsento a ricevere le e-mail Road Watch all’indirizzo verificato del mio account.",
    active: "Il consenso alle e-mail è attivo.",
    off: "Il consenso alle e-mail è inattivo.",
    verify: "Verifica l’e-mail del tuo account prima di attivare l’invio.",
    note: "Sono considerate solo le nuove modifiche al percorso dopo il consenso. L’attivazione non invia nuovamente la cronologia. Aprire un messaggio non contrassegna un aggiornamento come esaminato.",
    window:
      "Le e-mail considerano i cambiamenti attuali non esaminati delle ultime 48 ore. Un riepilogo giornaliero viene inviato al massimo una volta per giorno locale. Le autorizzazioni delle fonti e dei corridoi vengono ricontrollate prima dell’invio.",
    serviceOff:
      "Il servizio di invio non è disponibile. Puoi salvare le preferenze; l’invio richiede un servizio disponibile, fonti autorizzate e un percorso attivo.",
    uncertain:
      "L’esito di un precedente tentativo di invio è incerto e non verrà ripetuto automaticamente. Controlla la casella prima di chiedere una verifica al gestore.",
    preview: "Anteprima degli elementi e-mail da inviare",
    previewNote:
      "L’anteprima usa le preferenze salvate. Non invia alcuna e-mail.",
    none: "Nessun elemento idoneo è attualmente da inviare.",
    unavailable:
      "L’invio non è disponibile con il consenso, la fonte o lo stato del percorso attuali.",
    daily:
      "L’invio giornaliero è già stato tentato oggi. Gli altri aggiornamenti idonei attendono il prossimo invio previsto.",
    quiet: "Le ore di silenzio sono attive. Questi elementi attenderanno.",
    more: "L’anteprima mostra al massimo 50 elementi. Altri possono rimanere; consulta gli eventi del percorso.",
    save: "Salva preferenze e-mail",
  },
  "rm-CH": {
    consent:
      "Jau accept da retschaiver e-mails Road Watch a l’adressa verifitgada da mes conto.",
    active: "Il consentiment per e-mails è activ.",
    off: "Il consentiment per e-mails è inactiv.",
    verify: "Verifitgai l’adressa da vos conto avant d’activar la spediziun.",
    note: "Resguardadas vegnan mo novas midadas dal ruta suenter il consentiment. L’activaziun na trametta betg l’istorgia veglia. Avrir in messadi na marchescha betg ina midada sco controllada.",
    window:
      "Ils e-mails resguardan las midadas actualas betg controlladas da las ultimas 48 uras. Ina resumaziun vegn tramessa maximalmain ina giada per di local. Las permissiuns da las funtaunas e dals corridors vegnan controlladas danovamain avant la spediziun.",
    serviceOff:
      "Il servetsch da spediziun n’è betg disponibel. Vus pudais memorisar preferenzas; la spediziun dovra in servetsch disponibel, funtaunas permessas ed in ruta activ.",
    uncertain:
      "Il resultat d’ina tentativa anteriura d’e-mail è malsegir e na vegn betg repetì automaticamain. Controllai la chascha postala avant da dumandar ina controlla al gestiunari.",
    preview: "Prevista dals elements pronts per e-mail",
    previewNote:
      "La prevista dovra las preferenzas memorisadas. Ella na trametta nagin e-mail.",
    none: "Actualmain n’èn nagins elements adattads pronts.",
    unavailable:
      "La spediziun n’è betg disponibla cun il consentiment, la funtauna u il stadi dal ruta actual.",
    daily:
      "La spediziun quotidiana è gia vegnida empruvada oz. Ulteriuras midadas adattadas spetgan la proxima spediziun planisada.",
    quiet: "Las uras da ruaus èn activas. Quests elements spetgan.",
    more: "La prevista mussa maximalmain 50 elements. Ulteriurs pon restar; controllai ils eveniments dal ruta.",
    save: "Memorisar preferenzas dad e-mail",
  },
};
