import type { Locale } from "./i18n";
import { roadEmailCopy } from "./road-email-copy";

const specific = {
  "en-CH": {
    consent:
      "I agree to receive Auction Watch emails at my verified account address.",
    note: "New auction changes after consent and current ending-soon reminders are considered. Opening an email does not review a lot or place a bid.",
    window:
      "Current unreviewed changes are retained for email for up to 48 hours. Ending-soon reminders require a followed lot and a current known deadline. Daily email sends at most once per local day; quiet hours and source permissions are rechecked before sending.",
    serviceOff:
      "Email service is unavailable. Preferences can be saved; delivery needs an active profile, permitted current source evidence and an available sending service.",
    unavailable:
      "Delivery is unavailable under the current consent, source or profile state.",
    more: "The preview shows at most 50 items. Review Auction Watch for further changes and reminders.",
  },
  "de-CH": {
    consent:
      "Ich stimme Auction-Watch-E-Mails an meine bestätigte Kontoadresse zu.",
    note: "Berücksichtigt werden neue Auktionsänderungen nach der Zustimmung und aktuelle Erinnerungen an das Auktionsende. Das Öffnen einer E-Mail prüft kein Los und gibt kein Gebot ab.",
    window:
      "Aktuelle ungeprüfte Änderungen bleiben bis zu 48 Stunden für E-Mails relevant. Erinnerungen erfordern ein verfolgtes Los mit bekanntem aktuellem Endtermin. Höchstens eine tägliche E-Mail pro lokalem Tag; Ruhezeiten und Quellenrechte werden vor dem Versand erneut geprüft.",
    serviceOff:
      "Der E-Mail-Dienst ist nicht verfügbar. Sie können Einstellungen speichern; der Versand erfordert ein aktives Profil, erlaubte aktuelle Quelldaten und einen verfügbaren Versanddienst.",
    unavailable:
      "Der Versand ist mit der aktuellen Zustimmung, Quelle oder dem Profilstatus nicht verfügbar.",
    more: "Die Vorschau zeigt höchstens 50 Einträge. Weitere Änderungen und Erinnerungen finden Sie in Auction Watch.",
  },
  "fr-CH": {
    consent:
      "J’accepte les e-mails Auction Watch à l’adresse vérifiée de mon compte.",
    note: "Les nouveaux changements après le consentement et les rappels de fin prochaine sont considérés. Ouvrir un e-mail ne marque pas un lot comme examiné et ne place aucune enchère.",
    window:
      "Les changements actuels non examinés restent pertinents pour les e-mails pendant 48 heures. Les rappels exigent un lot suivi et une échéance actuelle connue. Un envoi quotidien au maximum par jour local ; les heures de silence et les droits des sources sont revérifiés avant l’envoi.",
    serviceOff:
      "Le service e-mail est indisponible. Les préférences peuvent être enregistrées ; l’envoi exige un profil actif, des données actuelles autorisées et un service disponible.",
    unavailable:
      "L’envoi est indisponible avec le consentement, la source ou l’état du profil actuels.",
    more: "L’aperçu montre au maximum 50 éléments. Consultez Auction Watch pour les autres changements et rappels.",
  },
  "it-CH": {
    consent:
      "Acconsento alle e-mail Auction Watch all’indirizzo verificato del mio account.",
    note: "Sono considerati i nuovi cambiamenti dopo il consenso e i promemoria di prossima conclusione. Aprire un’e-mail non esamina un lotto e non effettua offerte.",
    window:
      "I cambiamenti attuali non esaminati restano pertinenti per le e-mail per 48 ore. I promemoria richiedono un lotto seguito e una scadenza attuale nota. Al massimo un invio giornaliero per giorno locale; ore di silenzio e permessi delle fonti sono ricontrollati prima dell’invio.",
    serviceOff:
      "Il servizio e-mail non è disponibile. Puoi salvare le preferenze; l’invio richiede un profilo attivo, dati attuali autorizzati e un servizio disponibile.",
    unavailable:
      "L’invio non è disponibile con il consenso, la fonte o lo stato del profilo attuali.",
    more: "L’anteprima mostra al massimo 50 elementi. Consulta Auction Watch per gli altri cambiamenti e promemoria.",
  },
  "rm-CH": {
    consent:
      "Jau accept e-mails Auction Watch a l’adressa verifitgada da mes conto.",
    note: "Resguardadas vegnan novas midadas suenter il consentiment e regurdanzas actualas a la fin imminenta. Avrir in e-mail na controlla nagin lot e na fa nagina offerta.",
    window:
      "Midadas actualas betg controlladas restan relevantas per e-mails durant 48 uras. Regurdanzas dovran in lot suandà ed in termin actual enconuschent. Maximalmain in e-mail quotidian per di local; uras da ruaus e permissiuns vegnan controlladas avant la spediziun.",
    serviceOff:
      "Il servetsch dad e-mail n’è betg disponibel. Preferenzas pon vegnir memorisadas; la spediziun dovra in profil activ, datas actualas permessas ed in servetsch disponibel.",
    unavailable:
      "La spediziun n’è betg disponibla cun il consentiment, la funtauna u il stadi dal profil actual.",
    more: "La prevista mussa maximalmain 50 elements. Controllai Auction Watch per ulteriuras midadas e regurdanzas.",
  },
};
export const auctionEmailCopy = Object.fromEntries(
  Object.entries(specific).map(([locale, values]) => [
    locale,
    { ...roadEmailCopy[locale as Locale], ...values },
  ]),
) as Record<Locale, (typeof roadEmailCopy)[Locale]>;
