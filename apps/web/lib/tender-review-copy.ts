export const tenderReviewCopy = {
  "en-CH": {
    title: "Changes since your last review",
    help: "Each saved revision is listed in order. Later changes do not erase earlier ones; this is not a net interpretation of current requirements.",
    first:
      "No decision recorded yet. History starts with the first saved revision.",
    empty: "No later saved revision in this review window.",
    unavailable:
      "This revision's evidence is unavailable. The review history has a gap.",
  },
  "de-CH": {
    title: "Änderungen seit Ihrer letzten Prüfung",
    help: "Alle gespeicherten Versionen stehen in zeitlicher Reihenfolge. Spätere Änderungen löschen frühere nicht; dies ist keine abschliessende Auslegung der aktuellen Anforderungen.",
    first:
      "Noch kein Entscheid erfasst. Der Verlauf beginnt mit der ersten gespeicherten Version.",
    empty: "Keine spätere gespeicherte Version in diesem Prüfzeitraum.",
    unavailable:
      "Die Belege dieser Version sind nicht verfügbar. Der Prüfverlauf weist eine Lücke auf.",
  },
  "fr-CH": {
    title: "Modifications depuis votre dernier examen",
    help: "Chaque version enregistrée figure dans l'ordre chronologique. Les modifications ultérieures n'effacent pas les précédentes ; il ne s'agit pas d'une interprétation globale des exigences actuelles.",
    first:
      "Aucune décision enregistrée. L'historique commence à la première version conservée.",
    empty: "Aucune version ultérieure enregistrée dans cette période d'examen.",
    unavailable:
      "Les preuves de cette version sont indisponibles. L'historique d'examen comporte une lacune.",
  },
  "it-CH": {
    title: "Modifiche dall'ultima revisione",
    help: "Ogni versione salvata è elencata in ordine cronologico. Le modifiche successive non cancellano quelle precedenti; non si tratta di un'interpretazione complessiva dei requisiti attuali.",
    first:
      "Nessuna decisione registrata. La cronologia inizia dalla prima versione salvata.",
    empty:
      "Nessuna versione successiva salvata in questo periodo di revisione.",
    unavailable:
      "Le prove di questa versione non sono disponibili. La cronologia di revisione presenta una lacuna.",
  },
  "rm-CH": {
    title: "Midadas dapi Vossa ultima examinaziun",
    help: "Mintga versiun memorisada cumpara en urden cronologic. Midadas posteriuras na stizzan betg las anteriuras; quai n'è betg in'interpretaziun globala da las pretensiuns actualas.",
    first:
      "Anc nagina decisiun registrada. L'istorgia cumenza cun l'emprima versiun memorisada.",
    empty:
      "Nagina versiun posteriura memorisada en questa perioda d'examinaziun.",
    unavailable:
      "Las cumprovas da questa versiun n'èn betg disponiblas. L'istorgia d'examinaziun ha ina largia.",
  },
} satisfies Record<
  string,
  Record<"title" | "help" | "first" | "empty" | "unavailable", string>
>;
