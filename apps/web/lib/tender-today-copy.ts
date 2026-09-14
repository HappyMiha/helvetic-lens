import type { Locale } from "./i18n";
const en = {
  title: "Tender review queue",
  body: "Your saved opportunities and followed tenders across profiles. Summaries reflect the retained publication; open its exact evidence and all changes since your last decision before deciding.",
  pending: "Pending review",
  count: "Pending in this tender queue",
  observed: "Recorded by Helvetic Lens",
  next: "Next page",
  previous: "Previous page",
  open: "Open evidence and review",
  private: "Private to you. Legal-feed filters do not filter these cards.",
};
type Copy = Record<keyof typeof en, string>;
export const tenderTodayCopy: Record<Locale, Copy> = {
  "en-CH": en,
  "de-CH": {
    title: "Ausschreibungen zur Prüfung",
    body: "Ihre gespeicherten Chancen und verfolgten Ausschreibungen über alle Profile. Zusammenfassungen entsprechen der gespeicherten Publikation. Öffnen Sie den exakten Beleg und alle Änderungen seit Ihrer letzten Entscheidung, bevor Sie entscheiden.",
    pending: "Prüfung ausstehend",
    count: "Ausstehend in dieser Ausschreibungsübersicht",
    observed: "Von Helvetic Lens erfasst",
    next: "Nächste Seite",
    previous: "Vorherige Seite",
    open: "Belege öffnen und prüfen",
    private:
      "Nur für Sie sichtbar. Filter des Rechtsfeeds gelten nicht für diese Karten.",
  },
  "fr-CH": {
    title: "Appels d’offres à examiner",
    body: "Vos opportunités enregistrées et appels d’offres suivis, tous profils confondus. Les résumés reflètent la publication conservée. Ouvrez la preuve exacte et tous les changements depuis votre dernière décision avant de décider.",
    pending: "Examen en attente",
    count: "En attente dans cette liste d’appels d’offres",
    observed: "Enregistré par Helvetic Lens",
    next: "Page suivante",
    previous: "Page précédente",
    open: "Ouvrir les preuves et examiner",
    private:
      "Visible uniquement par vous. Les filtres du flux juridique ne filtrent pas ces cartes.",
  },
  "it-CH": {
    title: "Gare da esaminare",
    body: "Le tue opportunità salvate e le gare seguite in tutti i profili. I riepiloghi riflettono la pubblicazione conservata. Apri la prova esatta e tutte le modifiche dall’ultima decisione prima di decidere.",
    pending: "Esame in sospeso",
    count: "In sospeso in questa coda di gare",
    observed: "Registrato da Helvetic Lens",
    next: "Pagina successiva",
    previous: "Pagina precedente",
    open: "Apri le prove ed esamina",
    private:
      "Visibile solo a te. I filtri del flusso giuridico non filtrano queste schede.",
  },
  "rm-CH": {
    title: "Concurs da examinar",
    body: "Vossas pussaivladads memorisadas e Voss concurs suandads en tut ils profils. Ils resums reflecteschan la publicaziun conservada. Avri la cumprova exacta e tut las midadas dapi Vossa ultima decisiun avant che decider.",
    pending: "Examinaziun pendenta",
    count: "Pendent en questa glista da concurs",
    observed: "Registrà da Helvetic Lens",
    next: "Proxima pagina",
    previous: "Pagina precedenta",
    open: "Avrir las cumprovas ed examinar",
    private:
      "Visibel mo per Vus. Ils filters dal fluss giuridic na filtreschan betg questas chartas.",
  },
};
