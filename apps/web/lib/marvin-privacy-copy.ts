import type { Locale } from "./i18n";

export const marvinPrivacyCopy: Record<
  Locale,
  { pause: string; resume: string; paused: string }
> = {
  "en-CH": {
    pause: "Pause Marvin",
    resume: "Enable Marvin",
    paused:
      "While paused, Marvin makes no new context, conversation, model-status or job requests. Use Enable Marvin to return. Context stays detached until you attach it again; these choices are saved on this browser.",
  },
  "de-CH": {
    pause: "Marvin pausieren",
    resume: "Marvin aktivieren",
    paused:
      "Während der Pause stellt Marvin keine neuen Anfragen zu Kontext, Gesprächen, Modellstatus oder Aufträgen. Mit «Marvin aktivieren» kehren Sie zurück. Getrennter Kontext bleibt getrennt, bis Sie ihn wieder verbinden. Diese Auswahl wird in diesem Browser gespeichert.",
  },
  "fr-CH": {
    pause: "Mettre Marvin en pause",
    resume: "Activer Marvin",
    paused:
      "En pause, Marvin ne lance aucune nouvelle requête de contexte, de conversation, d’état du modèle ou de tâche. Utilisez « Activer Marvin » pour revenir. Le contexte reste détaché jusqu’à ce que vous le rattachiez. Ces choix sont enregistrés dans ce navigateur.",
  },
  "it-CH": {
    pause: "Metti Marvin in pausa",
    resume: "Attiva Marvin",
    paused:
      "Durante la pausa Marvin non invia nuove richieste di contesto, conversazione, stato del modello o attività. Usa «Attiva Marvin» per tornare. Il contesto resta scollegato finché non lo ricolleghi. Queste scelte vengono salvate in questo browser.",
  },
  "rm-CH": {
    pause: "Metter Marvin en pausa",
    resume: "Activar Marvin",
    paused:
      "Durant la pausa na trametta Marvin naginas novas dumondas davart context, discurs, stadi dal model u incumbensas. Cun «Activar Marvin» turnais Vus enavos. Il context resta separà fin che Vus al colliáis puspè. Questa tscherna vegn memorisada en quest navigatur.",
  },
};
