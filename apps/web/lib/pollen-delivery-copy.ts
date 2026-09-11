import type { Locale } from "./i18n";

type Copy = {
  title: string;
  note: string;
  digest: string;
  quiet: string;
  start: string;
  end: string;
  clock: string;
  mode: string;
  invalidQuiet: string;
};
export const pollenDeliveryCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Delivery preferences",
    note: "These are saved preferences only. Saving them does not start monitoring, authorize live email delivery or send messages.",
    digest: "Daily digest time",
    quiet: "Set quiet hours",
    start: "Quiet hours start",
    end: "Quiet hours end",
    clock:
      "Times use the selected time zone: {timezone}. Quiet hours may cross midnight. Live scheduling is not active.",
    mode: "Changing email mode clears the digest time. Disabling quiet hours clears that interval.",
    invalidQuiet: "Choose different start and end times for quiet hours.",
  },
  "de-CH": {
    title: "Versandpräferenzen",
    note: "Dies sind nur gespeicherte Präferenzen. Das Speichern startet keine Überwachung, erteilt keine Zustimmung zum tatsächlichen E-Mail-Versand und versendet keine Nachrichten.",
    digest: "Uhrzeit der täglichen Zusammenfassung",
    quiet: "Ruhezeiten festlegen",
    start: "Beginn der Ruhezeit",
    end: "Ende der Ruhezeit",
    clock:
      "Die Zeiten gelten in der gewählten Zeitzone: {timezone}. Ruhezeiten können über Mitternacht dauern. Der zeitgesteuerte Versand ist nicht aktiv.",
    mode: "Ein Wechsel des E-Mail-Modus löscht die Uhrzeit der Zusammenfassung. Das Deaktivieren der Ruhezeiten löscht deren Zeitraum.",
    invalidQuiet:
      "Wählen Sie unterschiedliche Start- und Endzeiten für die Ruhezeit.",
  },
  "fr-CH": {
    title: "Préférences d’envoi",
    note: "Il s’agit uniquement de préférences enregistrées. Les enregistrer ne démarre pas la surveillance, n’autorise pas l’envoi réel d’e-mails et n’envoie aucun message.",
    digest: "Heure du résumé quotidien",
    quiet: "Définir des heures de silence",
    start: "Début des heures de silence",
    end: "Fin des heures de silence",
    clock:
      "Les heures utilisent le fuseau choisi : {timezone}. La période de silence peut passer minuit. L’envoi planifié n’est pas actif.",
    mode: "Changer le mode e-mail efface l’heure du résumé. Désactiver les heures de silence efface leur intervalle.",
    invalidQuiet:
      "Choisissez des heures de début et de fin différentes pour la période de silence.",
  },
  "it-CH": {
    title: "Preferenze di invio",
    note: "Si tratta solo di preferenze salvate. Salvarle non avvia il monitoraggio, non autorizza l’invio effettivo di e-mail e non invia messaggi.",
    digest: "Ora del riepilogo giornaliero",
    quiet: "Imposta ore di silenzio",
    start: "Inizio delle ore di silenzio",
    end: "Fine delle ore di silenzio",
    clock:
      "Gli orari usano il fuso selezionato: {timezone}. Le ore di silenzio possono attraversare la mezzanotte. L’invio programmato non è attivo.",
    mode: "Cambiare la modalità e-mail cancella l’ora del riepilogo. Disattivare le ore di silenzio ne cancella l’intervallo.",
    invalidQuiet:
      "Scegliete orari di inizio e fine diversi per le ore di silenzio.",
  },
  "rm-CH": {
    title: "Preferenzas da spediziun",
    note: "Quai èn mo preferenzas memorisadas. Las memorisar na cumenza nagina surveglianza, na permetta nagina spediziun effectiva dad e-mails e na trametta nagins messadis.",
    digest: "Ura da la resumaziun quotidiana",
    quiet: "Fixar uras da ruaus",
    start: "Cumenzament da las uras da ruaus",
    end: "Fin da las uras da ruaus",
    clock:
      "Las uras valan en la zona d’urari tschernida: {timezone}. Las uras da ruaus pon passar sur mesanotg. La spediziun planisada n’è betg activa.",
    mode: "Midar il modus dad e-mail stizza l’ura da la resumaziun. Deactivar las uras da ruaus stizza lur interval.",
    invalidQuiet:
      "Tscherna uras differentas per il cumenzament e la fin da las uras da ruaus.",
  },
};
