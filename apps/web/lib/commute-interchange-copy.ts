import type { Locale } from "./i18n";

const en = {
  title: "Scheduled connections",
  note: "These are timetable rules, not a live guarantee or an accessible walking route. Check current conditions before travelling.",
  scheduled: "Scheduled gap (seconds)",
  minimum: "Source minimum (seconds)",
  recommended: "Recommended transfer point; no guaranteed connection.",
  timed: "Timed connection: the source expects the departing vehicle to wait.",
  minimum_met: "The timetable meets the source's minimum transfer time.",
  same_trip: "Continue on the same scheduled trip.",
  unverified: "No verified connection rule is available.",
  ambiguous: "Conflicting equally specific rules prevent confirmation.",
  forbidden: "The source prohibits this transfer.",
  insufficient_time: "The timetable leaves insufficient transfer time.",
  different_service_day:
    "The legs use different service days; this connection is not verified.",
  unsupported_linked_trip:
    "This linked-vehicle connection needs further verification.",
};
export const commuteInterchangeCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    title: "Geplante Anschlüsse",
    note: "Dies sind Fahrplanregeln, keine Live-Garantie oder barrierefreie Wegbeschreibung. Prüfen Sie vor der Fahrt die aktuelle Lage.",
    scheduled: "Geplanter Abstand (Sekunden)",
    minimum: "Mindestzeit der Quelle (Sekunden)",
    recommended: "Empfohlener Umsteigepunkt; kein garantierter Anschluss.",
    timed:
      "Abgestimmter Anschluss: Laut Quelle soll das abfahrende Fahrzeug warten.",
    minimum_met: "Der Fahrplan erfüllt die Mindestumsteigezeit der Quelle.",
    same_trip: "Mit derselben geplanten Fahrt weiterfahren.",
    unverified: "Keine verifizierte Anschlussregel verfügbar.",
    ambiguous:
      "Widersprüchliche gleich spezifische Regeln verhindern die Bestätigung.",
    forbidden: "Die Quelle untersagt diesen Umstieg.",
    insufficient_time: "Der Fahrplan lässt zu wenig Umsteigezeit.",
    different_service_day:
      "Die Abschnitte haben unterschiedliche Betriebstage; der Anschluss ist nicht verifiziert.",
    unsupported_linked_trip:
      "Diese Fahrzeugverknüpfung erfordert weitere Prüfung.",
  },
  "fr-CH": {
    title: "Correspondances prévues",
    note: "Il s’agit de règles horaires, pas d’une garantie en temps réel ni d’un itinéraire piéton accessible. Vérifiez la situation avant de voyager.",
    scheduled: "Intervalle prévu (secondes)",
    minimum: "Minimum de la source (secondes)",
    recommended: "Point de correspondance recommandé ; aucune garantie.",
    timed:
      "Correspondance coordonnée : la source prévoit que le véhicule au départ attende.",
    minimum_met:
      "L’horaire respecte le temps minimal de correspondance de la source.",
    same_trip: "Continuer sur la même course prévue.",
    unverified: "Aucune règle de correspondance vérifiée disponible.",
    ambiguous:
      "Des règles contradictoires de même spécificité empêchent la confirmation.",
    forbidden: "La source interdit cette correspondance.",
    insufficient_time:
      "L’horaire ne laisse pas assez de temps pour la correspondance.",
    different_service_day:
      "Les tronçons ont des jours de service différents ; la correspondance n’est pas vérifiée.",
    unsupported_linked_trip:
      "Cette liaison entre véhicules nécessite une vérification supplémentaire.",
  },
  "it-CH": {
    title: "Coincidenze previste",
    note: "Sono regole d’orario, non una garanzia in tempo reale né un percorso pedonale accessibile. Verifica le condizioni prima di viaggiare.",
    scheduled: "Intervallo previsto (secondi)",
    minimum: "Minimo della fonte (secondi)",
    recommended: "Punto di cambio consigliato; coincidenza non garantita.",
    timed:
      "Coincidenza coordinata: la fonte prevede che il veicolo in partenza attenda.",
    minimum_met: "L’orario rispetta il tempo minimo di cambio della fonte.",
    same_trip: "Prosegui sulla stessa corsa prevista.",
    unverified: "Nessuna regola di coincidenza verificata disponibile.",
    ambiguous:
      "Regole contrastanti di pari specificità impediscono la conferma.",
    forbidden: "La fonte vieta questo cambio.",
    insufficient_time: "L’orario non lascia abbastanza tempo per il cambio.",
    different_service_day:
      "Le tratte hanno giorni di servizio diversi; la coincidenza non è verificata.",
    unsupported_linked_trip:
      "Questo collegamento tra veicoli richiede un’ulteriore verifica.",
  },
  "rm-CH": {
    title: "Colliaziuns planisadas",
    note: "Quai èn reglas da l’urari, betg ina garanzia actuala u ina via accessibla a pe. Controllai la situaziun avant il viadi.",
    scheduled: "Interval planisà (secundas)",
    minimum: "Minimum da la funtauna (secundas)",
    recommended: "Punct da midada recumandà; nagina colliaziun garantida.",
    timed:
      "Colliaziun coordinada: la funtauna prevesa che il vehichel da partenza spetgia.",
    minimum_met:
      "L’urari ademplescha il temp minimal da midada da la funtauna.",
    same_trip: "Cuntinuar cun il medem curs planisà.",
    unverified: "Nagina regla da colliaziun verifitgada è disponibla.",
    ambiguous:
      "Reglas contradictoricas da medema specificitad impedeschan la conferma.",
    forbidden: "La funtauna scumonda questa midada.",
    insufficient_time: "L’urari na lascha betg avunda temp per midar.",
    different_service_day:
      "Ils trajects han differents dis da servetsch; la colliaziun n’è betg verifitgada.",
    unsupported_linked_trip:
      "Questa colliaziun tranter vehichels dovra in’ulteriura verificaziun.",
  },
};
