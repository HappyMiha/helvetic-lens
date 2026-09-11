import type { Locale } from "./i18n";
type Copy = {
  allergen: string;
  choose: string;
  nearby: string;
  forget: string;
  locating: string;
  denied: string;
  unavailable: string;
  timeout: string;
  privacy: string;
  distance: string;
  ordered: string;
  unknown: string;
  directory: string;
  source: string;
  terms: string;
  limits: string;
  coverage: string;
  observation: string;
  forecast: string;
  documentedObservation: string;
  documentedForecast: string;
  notEstablished: string;
  unverified: string;
  chooseAllergens: string;
};
export const pollenStationCopy: Record<Locale, Copy> = {
  "en-CH": {
    allergen: "Allergen",
    choose: "Choose a station",
    nearby: "Find nearby stations",
    forget: "Clear device location",
    locating: "Finding your approximate location…",
    denied: "Location permission was denied. You can choose a station by name.",
    unavailable: "Device location is unavailable. Choose a station by name.",
    timeout:
      "Finding your location took too long. Try again or choose a station by name.",
    privacy:
      "Only if you choose: your browser asks for location permission. We calculate distances here without sending or saving your coordinates. Select the station yourself.",
    distance: "Approximate straight-line distance",
    ordered:
      "Stations are now ordered by distance. Your selected station has not changed.",
    unknown:
      "This saved station is outside the dated directory. Its code is retained; choose a listed station if you want to change it.",
    directory: "Station directory captured",
    source: "Source: MeteoSwiss",
    terms: "Source terms",
    limits:
      "Station measurements and model estimates near stations do not describe the exact pollen level at your home. The nearest station is not a guarantee of representative local conditions.",
    coverage: "Channels for your selected allergens",
    observation: "Hourly measurements",
    forecast: "Model forecasts",
    documentedObservation: "A measurement parameter is documented.",
    documentedForecast: "A seasonal forecast variable is documented.",
    notEstablished: "No matching channel has been established.",
    unverified:
      "Current availability at this station has not been verified. This dated source overview does not load measurements or forecasts and does not make Start available. Daily periods and category scales require separate verification.",
    chooseAllergens:
      "Choose allergens to compare their measurement and forecast channels.",
  },
  "de-CH": {
    allergen: "Allergen",
    choose: "Station wählen",
    nearby: "Stationen in der Nähe finden",
    forget: "Gerätestandort löschen",
    locating: "Ungefährer Standort wird ermittelt…",
    denied:
      "Der Standortzugriff wurde abgelehnt. Sie können eine Station nach Namen wählen.",
    unavailable:
      "Der Gerätestandort ist nicht verfügbar. Wählen Sie eine Station nach Namen.",
    timeout:
      "Die Standortbestimmung hat zu lange gedauert. Versuchen Sie es erneut oder wählen Sie eine Station nach Namen.",
    privacy:
      "Nur auf Wunsch: Ihr Browser fragt nach der Standortfreigabe. Die Entfernungen werden hier berechnet, ohne Ihre Koordinaten zu senden oder zu speichern. Wählen Sie die Station selbst.",
    distance: "Ungefähre Luftlinie",
    ordered:
      "Die Stationen sind jetzt nach Entfernung sortiert. Ihre ausgewählte Station bleibt unverändert.",
    unknown:
      "Diese gespeicherte Station fehlt im datierten Verzeichnis. Ihr Code bleibt erhalten; wählen Sie eine aufgeführte Station, um ihn zu ändern.",
    directory: "Stationsverzeichnis erfasst am",
    source: "Quelle: MeteoSchweiz",
    terms: "Nutzungsbedingungen der Quelle",
    limits:
      "Stationsmessungen und Modellschätzungen nahe den Stationen zeigen nicht die genaue Pollenbelastung bei Ihnen zu Hause. Die nächste Station garantiert keine repräsentativen örtlichen Bedingungen.",
    coverage: "Kanäle für Ihre ausgewählten Allergene",
    observation: "Stündliche Messungen",
    forecast: "Modellprognosen",
    documentedObservation: "Ein Messparameter ist dokumentiert.",
    documentedForecast: "Eine saisonale Prognosevariable ist dokumentiert.",
    notEstablished: "Ein entsprechender Kanal wurde nicht nachgewiesen.",
    unverified:
      "Die aktuelle Verfügbarkeit an dieser Station ist nicht geprüft. Diese datierte Quellenübersicht lädt keine Messungen oder Prognosen und ermöglicht keinen Start. Tageszeiträume und Kategorieskalen müssen separat geprüft werden.",
    chooseAllergens:
      "Wählen Sie Allergene, um deren Mess- und Prognosekanäle zu vergleichen.",
  },
  "fr-CH": {
    allergen: "Allergène",
    choose: "Choisir une station",
    nearby: "Trouver les stations proches",
    forget: "Effacer la position de l’appareil",
    locating: "Recherche de votre position approximative…",
    denied:
      "L’accès à la position a été refusé. Vous pouvez choisir une station par son nom.",
    unavailable:
      "La position de l’appareil est indisponible. Choisissez une station par son nom.",
    timeout:
      "La recherche de position a pris trop de temps. Réessayez ou choisissez une station par son nom.",
    privacy:
      "Uniquement si vous le souhaitez : le navigateur demande l’accès à votre position. Les distances sont calculées ici sans envoyer ni enregistrer vos coordonnées. Choisissez vous-même la station.",
    distance: "Distance approximative à vol d’oiseau",
    ordered:
      "Les stations sont maintenant classées par distance. La station sélectionnée n’a pas changé.",
    unknown:
      "Cette station enregistrée ne figure pas dans le répertoire daté. Son code est conservé ; choisissez une station de la liste pour le modifier.",
    directory: "Répertoire des stations relevé le",
    source: "Source : MétéoSuisse",
    terms: "Conditions de la source",
    limits:
      "Les mesures des stations et les estimations du modèle à proximité ne décrivent pas le niveau exact de pollen chez vous. La station la plus proche ne garantit pas des conditions locales représentatives.",
    coverage: "Canaux pour les allergènes sélectionnés",
    observation: "Mesures horaires",
    forecast: "Prévisions du modèle",
    documentedObservation: "Un paramètre de mesure est documenté.",
    documentedForecast: "Une variable de prévision saisonnière est documentée.",
    notEstablished: "Aucun canal correspondant n’a été établi.",
    unverified:
      "La disponibilité actuelle à cette station n’a pas été vérifiée. Cet aperçu daté ne charge ni mesures ni prévisions et ne permet pas le démarrage. Les périodes journalières et les échelles de catégories nécessitent une vérification séparée.",
    chooseAllergens:
      "Choisissez des allergènes pour comparer leurs canaux de mesure et de prévision.",
  },
  "it-CH": {
    allergen: "Allergene",
    choose: "Scegli una stazione",
    nearby: "Trova stazioni vicine",
    forget: "Cancella la posizione del dispositivo",
    locating: "Ricerca della posizione approssimativa…",
    denied:
      "Il permesso di localizzazione è stato negato. Puoi scegliere una stazione per nome.",
    unavailable:
      "La posizione del dispositivo non è disponibile. Scegli una stazione per nome.",
    timeout:
      "La ricerca della posizione ha richiesto troppo tempo. Riprova o scegli una stazione per nome.",
    privacy:
      "Solo se lo desideri: il browser chiede il permesso di localizzazione. Le distanze vengono calcolate qui senza inviare o salvare le coordinate. Scegli tu la stazione.",
    distance: "Distanza approssimativa in linea d’aria",
    ordered:
      "Le stazioni sono ora ordinate per distanza. La stazione selezionata non è cambiata.",
    unknown:
      "Questa stazione salvata non è presente nell’elenco datato. Il codice è conservato; scegli una stazione elencata per modificarlo.",
    directory: "Elenco delle stazioni rilevato il",
    source: "Fonte: MeteoSvizzera",
    terms: "Condizioni della fonte",
    limits:
      "Le misurazioni delle stazioni e le stime del modello nelle vicinanze non descrivono il livello esatto di polline a casa tua. La stazione più vicina non garantisce condizioni locali rappresentative.",
    coverage: "Canali per gli allergeni selezionati",
    observation: "Misurazioni orarie",
    forecast: "Previsioni del modello",
    documentedObservation: "Un parametro di misurazione è documentato.",
    documentedForecast: "Una variabile di previsione stagionale è documentata.",
    notEstablished: "Non è stato accertato un canale corrispondente.",
    unverified:
      "La disponibilità attuale presso questa stazione non è stata verificata. Questa panoramica datata non carica misurazioni o previsioni e non consente l’avvio. I periodi giornalieri e le scale delle categorie richiedono verifiche separate.",
    chooseAllergens:
      "Scegli gli allergeni per confrontare i canali di misurazione e previsione.",
  },
  "rm-CH": {
    allergen: "Allergen",
    choose: "Tscherner ina staziun",
    nearby: "Chattar staziuns vischinas",
    forget: "Stizzar la posiziun da l’apparat",
    locating: "Tschertgar tia posiziun approximativa…",
    denied:
      "L’access a la posiziun è vegnì refusà. Ti pos tscherner ina staziun tenor num.",
    unavailable:
      "La posiziun da l’apparat n’è betg disponibla. Tscherna ina staziun tenor num.",
    timeout:
      "La tschertga da la posiziun ha durà memia ditg. Emprova danovamain u tscherna ina staziun tenor num.",
    privacy:
      "Mo sin tes giavisch: il navigatur dumonda il permiss per la posiziun. Las distanzas vegnan calculadas qua senza trametter u memorisar tias coordinatas. Tscherna sez la staziun.",
    distance: "Distanza approximativa en lingia directa",
    ordered:
      "Las staziuns èn ussa ordinadas tenor distanza. La staziun tschernida n’è betg vegnida midada.",
    unknown:
      "Questa staziun memorisada manca en il register datà. Ses code resta; tscherna ina staziun da la glista per al midar.",
    directory: "Register da staziuns registrà ils",
    source: "Funtauna: MeteoSvizra",
    terms: "Cundiziuns da la funtauna",
    limits:
      "Las mesiraziuns da staziuns e las stimaziuns dal model vischin a las staziuns na descrivan betg il nivel exact da pollen tar tai a chasa. La staziun la pli vischina na garantescha betg cundiziuns localas represchentativas.",
    coverage: "Chanals per ils allergens tschernids",
    observation: "Mesiraziuns uraras",
    forecast: "Previsiuns dal model",
    documentedObservation: "In parameter da mesiraziun è documentà.",
    documentedForecast: "Ina variabla da previsiun stagiunala è documentada.",
    notEstablished: "Nagin chanal correspundent è vegnì confermà.",
    unverified:
      "La disponibladad actuala a questa staziun n’è betg verifitgada. Questa survista datada na chargia naginas mesiraziuns u previsiuns e na permetta betg da cumenzar. Periodas quotidianas e scalas da categorias dovran ina verificaziun separada.",
    chooseAllergens:
      "Tscherna allergens per cumparegliar lur chanals da mesiraziun e previsiun.",
  },
};
