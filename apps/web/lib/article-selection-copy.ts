import type { Locale } from "./i18n";

export const articleSelectionCopy: Record<
  Locale,
  {
    questions: string[]; singleVersion: string; article: string; endExample: string; mode: string;
    whole: string;
    selected: string;
    from: string;
    to: string;
    help: string;
    articles: string;
    officialDate: string;
    unknown: string;
    scope: string;
    limits: string;
    ask: string;
    snapshot: string;
    text: string;
    source: string;
    historical: string;
  }
> = {
  "en-CH": {
    singleVersion: "One saved version", questions: ["Summarise the saved articles with citations.", "Which questions cannot be answered from these articles alone?"],
    article: "Art.", endExample: "323b",
    mode: "Document scope",
    whole: "Whole document",
    selected: "Selected articles",
    from: "First article",
    to: "Last article",
    help: "German Fedlex laws: one continuous range, including lettered articles (for example 319–323b). A different range creates a separate monitored document.",
    articles: "Articles found",
    officialDate: "Official version date",
    unknown: "Not provided by the source",
    scope: "Analysis scope",
    limits:
      "Only the saved articles are included. Other provisions, case law and the specific contract need separate review. Statutory text and interpretation must be distinguished.",
    ask: "Ask about saved text",
    snapshot:
      "Questions about one saved version. No comparison of two editions has been made.",
    text: "Open saved articles",
    source: "Official article",
    historical:
      "Import an official historical German Fedlex HTML URL of the same law. The saved article range also applies to this import.",
  },
  "de-CH": {
    singleVersion: "Eine gespeicherte Fassung", questions: ["Fasse die gespeicherten Artikel mit Belegen zusammen.", "Welche Fragen können anhand dieser Artikel allein nicht beantwortet werden?"],
    article: "Art.", endExample: "323b",
    mode: "Dokumentumfang",
    whole: "Ganzes Dokument",
    selected: "Ausgewählte Artikel",
    from: "Erster Artikel",
    to: "Letzter Artikel",
    help: "Deutsche Fedlex-Gesetze: ein zusammenhängender Bereich einschliesslich Buchstabenartikeln (z. B. 319–323b). Ein anderer Bereich wird als separates Dokument überwacht.",
    articles: "Gefundene Artikel",
    officialDate: "Datum der amtlichen Fassung",
    unknown: "Von der Quelle nicht angegeben",
    scope: "Analysebereich",
    limits:
      "Enthalten sind nur die gespeicherten Artikel. Weitere Vorschriften, Rechtsprechung und der konkrete Vertrag sind gesondert zu prüfen. Gesetzestext und Einordnung sind zu unterscheiden.",
    ask: "Gespeicherten Text befragen",
    snapshot:
      "Fragen zu einer gespeicherten Fassung. Es wurden keine zwei Fassungen verglichen.",
    text: "Gespeicherte Artikel öffnen",
    source: "Amtlicher Artikel",
    historical:
      "Eine amtliche historische deutsche Fedlex-HTML-URL desselben Gesetzes importieren. Der gespeicherte Artikelbereich gilt auch für diesen Import.",
  },
  "fr-CH": {
    singleVersion: "Une version enregistrée", questions: ["Résume les articles enregistrés avec des citations.", "Quelles questions ne peuvent pas être résolues avec ces seuls articles ?"],
    article: "Art.", endExample: "323b",
    mode: "Périmètre du document",
    whole: "Document entier",
    selected: "Articles sélectionnés",
    from: "Premier article",
    to: "Dernier article",
    help: "Lois Fedlex en allemand : une plage continue, y compris les articles avec lettres (p. ex. 319–323b). Une autre plage crée un document suivi distinct.",
    articles: "Articles trouvés",
    officialDate: "Date de la version officielle",
    unknown: "Non indiquée par la source",
    scope: "Périmètre de l’analyse",
    limits:
      "Seuls les articles enregistrés sont inclus. Les autres dispositions, la jurisprudence et le contrat concret nécessitent un examen séparé. Le texte légal et son interprétation doivent être distingués.",
    ask: "Interroger le texte enregistré",
    snapshot:
      "Questions sur une seule version enregistrée. Aucune comparaison de deux versions n’a été effectuée.",
    text: "Ouvrir les articles enregistrés",
    source: "Article officiel",
    historical:
      "Importer une URL HTML Fedlex officielle historique en allemand de la même loi. La plage enregistrée s’applique aussi à cet import.",
  },
  "it-CH": {
    singleVersion: "Una versione salvata", questions: ["Riassumi gli articoli salvati con citazioni.", "Quali domande non possono essere risolte con questi soli articoli?"],
    article: "Art.", endExample: "323b",
    mode: "Ambito del documento",
    whole: "Documento completo",
    selected: "Articoli selezionati",
    from: "Primo articolo",
    to: "Ultimo articolo",
    help: "Leggi Fedlex in tedesco: un intervallo continuo, inclusi gli articoli con lettere (ad es. 319–323b). Un intervallo diverso crea un documento monitorato separato.",
    articles: "Articoli trovati",
    officialDate: "Data della versione ufficiale",
    unknown: "Non indicata dalla fonte",
    scope: "Ambito dell’analisi",
    limits:
      "Sono inclusi solo gli articoli salvati. Altre disposizioni, la giurisprudenza e il contratto concreto richiedono un esame separato. Occorre distinguere il testo di legge dall’interpretazione.",
    ask: "Interroga il testo salvato",
    snapshot:
      "Domande su una sola versione salvata. Non sono state confrontate due versioni.",
    text: "Apri gli articoli salvati",
    source: "Articolo ufficiale",
    historical:
      "Importa un URL HTML Fedlex ufficiale storico in tedesco della stessa legge. L’intervallo salvato si applica anche a questa importazione.",
  },
  "rm-CH": {
    singleVersion: "Ina versiun memorisada", questions: ["Resumescha ils artitgels memorisads cun citats.", "Tge dumondas na pon betg vegnir respundidas mo cun quests artitgels?"],
    article: "Art.", endExample: "323b",
    mode: "Dimensiun dal document",
    whole: "Document cumplet",
    selected: "Artitgels tschernids",
    from: "Emprim artitgel",
    to: "Ultim artitgel",
    help: "Les da Fedlex en tudestg: in interval cuntinuà, inclus artitgels cun bustabs (p. ex. 319–323b). In auter interval vegn surveglià sco document separà.",
    articles: "Artitgels chattads",
    officialDate: "Data da la versiun uffiziala",
    unknown: "Betg inditgada da la funtauna",
    scope: "Sectur da l’analisa",
    limits:
      "Mo ils artitgels memorisads èn inclus. Ulteriuras prescripziuns, la giurisprudenza ed il contract concret dovran ina examinaziun separada. Il text da lescha e l’interpretaziun ston vegnir distinguids.",
    ask: "Interrogar il text memorisà",
    snapshot:
      "Dumondas davart ina versiun memorisada. Duas versiuns n’èn betg vegnidas cumparegliadas.",
    text: "Avrir ils artitgels memorisads",
    source: "Artitgel uffizial",
    historical:
      "Importar ina URL HTML uffiziala istorica da Fedlex en tudestg da la medema lescha. L’interval memorisà vala er per quest import.",
  },
};
