import type { Locale } from "./i18n";
type Copy = {
  boundary: string;
  more: string;
  reason: string;
  documents: string;
  open: string;
  selection: string;
  open_list: string;
  event_limit: string;
};
export const digestInterestCopy: Record<Locale, Copy> = {
  "en-CH": {
    boundary:
      "Saved topic matches are not confirmed legal impacts. Unknown means impact has not been assessed.",
    more: "Up to five topics and five directly monitored documents are shown. Open the event for all current interests and evidence.",
    reason: "Matched terms",
    documents: "Directly monitored documents",
    open: "Open event and evidence",
    selection:
      "Topic-only and directly watched events without an impact assessment require Unknown, or no severity filter. No new AI request is made.",
    open_list: "Open Today",
    event_limit:
      "This digest is limited to 50 events. Open Today for all current interests, or narrow your source and severity filters.",
  },
  "de-CH": {
    boundary:
      "Gespeicherte Thementreffer sind keine bestätigten rechtlichen Auswirkungen. Unbekannt bedeutet, dass die Auswirkung nicht bewertet wurde.",
    more: "Bis zu fünf Themen und fünf direkt überwachte Dokumente werden angezeigt. Öffnen Sie das Ereignis für alle aktuellen Interessen und Belege.",
    reason: "Übereinstimmende Begriffe",
    documents: "Direkt überwachte Dokumente",
    open: "Ereignis und Belege öffnen",
    selection:
      "Thementreffer und direkt überwachte Ereignisse ohne Auswirkungsbewertung erfordern Unbekannt oder keinen Schweregradfilter. Es erfolgt keine neue KI-Anfrage.",
    open_list: "Heute öffnen",
    event_limit:
      "Diese Zusammenfassung ist auf 50 Ereignisse begrenzt. Öffnen Sie Heute für alle aktuellen Interessen oder grenzen Sie Quellen und Schweregrade ein.",
  },
  "fr-CH": {
    boundary:
      "Les correspondances thématiques enregistrées ne sont pas des impacts juridiques confirmés. Inconnu signifie que l’impact n’a pas été évalué.",
    more: "Au maximum cinq sujets et cinq documents directement surveillés sont affichés. Ouvrez l’événement pour tous les intérêts actuels et les preuves.",
    reason: "Termes correspondants",
    documents: "Documents directement surveillés",
    open: "Ouvrir l’événement et les preuves",
    selection:
      "Les correspondances thématiques et événements surveillés sans évaluation d’impact nécessitent Inconnu ou aucun filtre de gravité. Aucune nouvelle requête IA.",
    open_list: "Ouvrir Aujourd’hui",
    event_limit:
      "Cette synthèse est limitée à 50 événements. Ouvrez Aujourd’hui pour tous les intérêts actuels ou affinez les sources et la gravité.",
  },
  "it-CH": {
    boundary:
      "Le corrispondenze tematiche salvate non sono impatti giuridici confermati. Sconosciuto significa che l’impatto non è stato valutato.",
    more: "Sono mostrati fino a cinque temi e cinque documenti monitorati direttamente. Apri l’evento per tutti gli interessi attuali e le prove.",
    reason: "Termini corrispondenti",
    documents: "Documenti monitorati direttamente",
    open: "Apri evento e prove",
    selection:
      "Le corrispondenze tematiche e gli eventi monitorati senza valutazione d’impatto richiedono Sconosciuto o nessun filtro di gravità. Nessuna nuova richiesta IA.",
    open_list: "Apri Oggi",
    event_limit:
      "Questo riepilogo è limitato a 50 eventi. Apri Oggi per tutti gli interessi attuali o restringi fonti e gravità.",
  },
  "rm-CH": {
    boundary:
      "Correspundenzas tematicas memorisadas n’èn betg effects giuridics confermads. Nunenconuschent signifitga che l’effect n’è betg vegnì valità.",
    more: "Fin a tschintg temas e tschintg documents survegliads directamain vegnan mussads. Avra l’eveniment per tut ils interess actuals e las cumprovas.",
    reason: "Noziuns correspundentas",
    documents: "Documents survegliads directamain",
    open: "Avrir l’eveniment e las cumprovas",
    selection:
      "Correspundenzas tematicas ed eveniments survegliads senza valitaziun da l’effect dovran Nunenconuschent u nagin filter da gravitad. Nagina nova dumonda IA.",
    open_list: "Avrir Oz",
    event_limit:
      "Questa resumaziun è limitada a 50 eveniments. Avra Oz per tut ils interess actuals u restrenscha las funtaunas e la gravitad.",
  },
};
