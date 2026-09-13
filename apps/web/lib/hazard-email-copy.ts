import type { Locale } from "./i18n";
import { roadEmailCopy } from "./road-email-copy";

export const hazardEmailCopy: typeof roadEmailCopy = {
  "en-CH": {
    ...roadEmailCopy["en-CH"],
    consent: "I agree to receive Hazard Watch emails at my verified account address.",
    note: "Only new material warning changes after your consent are considered. Enabling email does not resend history. Receiving an email does not mark a warning reviewed. Open the official instructions before acting.",
    window: "Email considers current unreviewed changes from the last 48 hours. A daily digest sends at most once per local day. Source rights, saved area, consent, review and mute are checked again before sending. The same source change across your saved places is sent once.",
    serviceOff: "The sending service is unavailable. You can save preferences; delivery requires an available service, permitted source and active place.",
    unavailable: "Delivery is unavailable under the current consent, source or saved place state.",
    more: "The preview shows at most 50 items. Further updates may remain; review the saved place warnings.",
  },
  "de-CH": {
    ...roadEmailCopy["de-CH"],
    consent: "Ich stimme zu, Hazard-Watch-E-Mails an meine bestätigte Konto-Adresse zu erhalten.",
    note: "Berücksichtigt werden nur neue wesentliche Warnungsänderungen nach Ihrer Zustimmung. Die Aktivierung versendet keine Historie erneut. Ein empfangenes E-Mail markiert keine Warnung als geprüft. Lesen Sie vor dem Handeln die offiziellen Anweisungen.",
    window: "E-Mail berücksichtigt aktuelle ungeprüfte Änderungen der letzten 48 Stunden. Die Tagesübersicht wird höchstens einmal pro lokalem Tag versandt. Quellenrechte, gespeichertes Gebiet, Zustimmung, Prüfung und Stummschaltung werden vor dem Versand erneut geprüft. Dieselbe Quellenänderung für mehrere Ihrer Orte wird einmal versandt.",
    serviceOff: "Der Versanddienst ist nicht verfügbar. Einstellungen können gespeichert werden; der Versand benötigt einen verfügbaren Dienst, eine zulässige Quelle und einen aktiven Ort.",
    unavailable: "Der Versand ist mit der aktuellen Zustimmung, Quelle oder dem Zustand des gespeicherten Orts nicht verfügbar.",
    more: "Die Vorschau zeigt höchstens 50 Einträge. Weitere Änderungen sind möglich; prüfen Sie die Warnungen des gespeicherten Orts.",
  },
  "fr-CH": {
    ...roadEmailCopy["fr-CH"],
    consent: "J’accepte de recevoir les e-mails Hazard Watch à l’adresse vérifiée de mon compte.",
    note: "Seuls les nouveaux changements importants d’alertes après votre consentement sont considérés. L’activation ne renvoie pas l’historique. Recevoir un e-mail ne marque pas l’alerte comme examinée. Lisez les consignes officielles avant d’agir.",
    window: "Les e-mails concernent les changements actuels non examinés des dernières 48 heures. Le récapitulatif est envoyé au plus une fois par jour local. Droits de la source, zone enregistrée, consentement, examen et sourdine sont revérifiés avant l’envoi. Un même changement de source concernant plusieurs de vos lieux est envoyé une seule fois.",
    serviceOff: "Le service d’envoi est indisponible. Vous pouvez enregistrer vos préférences ; l’envoi exige un service disponible, une source autorisée et un lieu actif.",
    unavailable: "L’envoi est indisponible avec le consentement, la source ou l’état actuel du lieu enregistré.",
    more: "L’aperçu affiche au plus 50 éléments. D’autres changements peuvent rester ; consultez les alertes du lieu enregistré.",
  },
  "it-CH": {
    ...roadEmailCopy["it-CH"],
    consent: "Acconsento a ricevere le e-mail Hazard Watch all’indirizzo verificato del mio account.",
    note: "Sono considerate solo le nuove modifiche sostanziali agli avvisi dopo il consenso. L’attivazione non reinvia la cronologia. Ricevere un’e-mail non contrassegna l’avviso come esaminato. Leggi le istruzioni ufficiali prima di agire.",
    window: "Le e-mail riguardano le modifiche attuali non esaminate delle ultime 48 ore. Il riepilogo viene inviato al massimo una volta per giorno locale. Diritti della fonte, area salvata, consenso, esame e silenziamento sono ricontrollati prima dell’invio. La stessa modifica della fonte per più luoghi viene inviata una volta sola.",
    serviceOff: "Il servizio di invio non è disponibile. Puoi salvare le preferenze; l’invio richiede un servizio disponibile, una fonte autorizzata e un luogo attivo.",
    unavailable: "L’invio non è disponibile con il consenso, la fonte o lo stato attuale del luogo salvato.",
    more: "L’anteprima mostra al massimo 50 elementi. Potrebbero esserci altre modifiche; consulta gli avvisi del luogo salvato.",
  },
  "rm-CH": {
    ...roadEmailCopy["rm-CH"],
    consent: "Jau sun d’accord da retschaiver e-mails Hazard Watch a l’adressa verifitgada da mes conto.",
    note: "Resguardadas vegnan mo novas midadas essenzialas d’avertiments suenter Voss consentiment. L’activaziun na trametta betg danovamain l’istorgia. Retschaiver in e-mail na marca betg l’avertiment sco controllà. Legiai las instrucziuns uffizialas avant d’agir.",
    window: "Ils e-mails resguardan midadas actualas betg controlladas da las ultimas 48 uras. La survista quotidiana vegn tramessa maximalmain ina giada per di local. Dretgs da la funtauna, territori memorisà, consentiment, controlla e silenzi vegnan verifitgads danovamain avant la spediziun. La medema midada per plirs da Voss lieus vegn tramessa ina giada.",
    serviceOff: "Il servetsch da spediziun n’è betg disponibel. Vus pudais memorisar preferenzas; la spediziun dovra in servetsch disponibel, ina funtauna permessa ed in lieu activ.",
    unavailable: "La spediziun n’è betg disponibla cun il consentiment, la funtauna u il stadi actual dal lieu memorisà.",
    more: "La prevista mussa maximalmain 50 endataziuns. Ulteriuras midadas pon restar; consultai ils avertiments dal lieu memorisà.",
  },
} satisfies Record<Locale, Record<keyof typeof roadEmailCopy["en-CH"], string>>;
