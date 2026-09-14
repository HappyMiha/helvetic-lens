import type { Locale } from "./i18n";
const en = {
  title: "Monitoring email preferences",
  note: "Choose one of your monitors to review its email schedule, quiet hours and consent. Each monitor keeps its own settings. Opening this page sends nothing.",
  select: "Choose a saved monitor",
  close: "Close settings",
  pollen:
    "To change a running Pollen schedule, explicitly pause monitoring first. Saving keeps it paused and turns email consent off. Resume separately after reviewing the saved schedule and current source availability.",
  save: "Save email schedule",
  saved: "Saved. Review the current settings below.",
  boundary:
    "Source checks, in-app reviews and email consent have separate controls. Saving email preferences does not start a monitor. Legal digests have separate settings.",
};
export const monitoringEmailCentreCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    title: "Monitoring-E-Mail-Einstellungen",
    note: "Wählen Sie eine Ihrer Überwachungen, um Versandzeit, Ruhezeiten und Zustimmung zu prüfen. Jede Überwachung behält ihre eigenen Einstellungen. Das Öffnen dieser Seite versendet nichts.",
    select: "Gespeicherte Überwachung auswählen",
    close: "Einstellungen schliessen",
    pollen:
      "Pausieren Sie eine laufende Pollen-Überwachung ausdrücklich, bevor Sie den Versandplan ändern. Nach dem Speichern bleibt sie pausiert und die E-Mail-Zustimmung ist aus. Prüfen Sie den gespeicherten Plan und die Quellenverfügbarkeit vor dem separaten Fortsetzen.",
    save: "E-Mail-Zeitplan speichern",
    saved: "Gespeichert. Prüfen Sie die aktuellen Einstellungen unten.",
    boundary:
      "Quellenabfragen, Prüfungen in der App und E-Mail-Zustimmung haben separate Einstellungen. Das Speichern startet keine Überwachung. Rechtliche Zusammenfassungen haben eigene Einstellungen.",
  },
  "fr-CH": {
    title: "Préférences e-mail du monitoring",
    note: "Choisissez un de vos suivis pour vérifier son horaire, ses heures calmes et votre consentement. Chaque suivi conserve ses réglages. Ouvrir cette page ne transmet rien.",
    select: "Choisir un suivi enregistré",
    close: "Fermer les réglages",
    pollen:
      "Mettez explicitement le suivi Pollen en pause avant de modifier son horaire. Il reste en pause après enregistrement et le consentement e-mail est désactivé. Reprenez séparément après avoir vérifié les réglages et la disponibilité des sources.",
    save: "Enregistrer l’horaire e-mail",
    saved: "Enregistré. Vérifiez les réglages actuels ci-dessous.",
    boundary:
      "Les contrôles des sources, les revues dans l’application et le consentement e-mail sont distincts. Enregistrer ne démarre aucun suivi. Les résumés juridiques ont leurs propres réglages.",
  },
  "it-CH": {
    title: "Preferenze e-mail del monitoraggio",
    note: "Scegli un tuo monitoraggio per controllare orario, ore di silenzio e consenso. Ogni monitoraggio mantiene le proprie impostazioni. Aprire questa pagina non invia nulla.",
    select: "Scegli un monitoraggio salvato",
    close: "Chiudi impostazioni",
    pollen:
      "Metti esplicitamente in pausa il monitoraggio Pollen prima di cambiare l’orario. Il salvataggio lo mantiene in pausa e disattiva il consenso e-mail. Riprendi separatamente dopo aver controllato le impostazioni e la disponibilità delle fonti.",
    save: "Salva orario e-mail",
    saved: "Salvato. Controlla le impostazioni attuali qui sotto.",
    boundary:
      "Controlli delle fonti, revisioni nell’app e consenso e-mail hanno comandi separati. Salvare non avvia un monitoraggio. I riepiloghi giuridici hanno impostazioni proprie.",
  },
  "rm-CH": {
    title: "Preferenzas dad e-mail dal monitoring",
    note: "Tscherna in da tes monitorings per controllar l’urari, las uras da ruaus ed il consentiment. Mintga monitoring mantegna sias atgnas configuraziuns. Avrir questa pagina na trametta nagut.",
    select: "Tscherner in monitoring memorisà",
    close: "Serrar las configuraziuns",
    pollen:
      "Metta explicitamain en pausa il monitoring Pollen avant che midar l’urari. Memorisar al lascha en pausa e disactivescha il consentiment dad e-mail. Cuntinuescha separadamain suenter avair controllà las configuraziuns e la disponibladad da las funtaunas.",
    save: "Memorisar l’urari dad e-mail",
    saved: "Memorisà. Controlla las configuraziuns actualas sutvart.",
    boundary:
      "Las controllas da funtaunas, las controllas en l’app ed il consentiment dad e-mail han configuraziuns separadas. Memorisar na cumenza nagin monitoring. Ils resums giuridics han atgnas configuraziuns.",
  },
};
