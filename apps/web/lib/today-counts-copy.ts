import type { Locale } from "./i18n";

type Copy = {
  title: string;
  body: string;
  total: string;
  legal: string;
  loading: string;
  error: string;
  incomplete: string;
  unavailable: string;
  refresh: string;
  checked: string;
  empty: string;
};

export const todayCountsCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Changes awaiting review",
    total: "Total",
    legal: "Legal monitoring",
    body: "Unread changes in your nine Monitoring sections and legal feed, across all pages. Each section keeps its Today time window. Counts describe readable saved changes; source availability is shown in each section. Legal filters below do not change this overview.",
    loading: "Counting review queues…",
    error: "Review counts could not be loaded. Open a section or retry.",
    incomplete:
      "A complete total is unavailable. Open the sections to review their full queues.",
    unavailable: "Count unavailable",
    refresh: "Refresh review counts",
    checked: "Checked",
    empty:
      "No readable changes await review in these queues. This does not confirm source coverage.",
  },
  "de-CH": {
    title: "Änderungen zur Prüfung",
    total: "Gesamt",
    legal: "Rechtsmonitoring",
    body: "Ungelesene Änderungen in Ihren neun Monitoring-Bereichen und im Rechtsfeed, über alle Seiten. Jeder Bereich behält sein Heute-Zeitfenster. Gezählt werden lesbare gespeicherte Änderungen; die Quellenverfügbarkeit steht im jeweiligen Bereich. Die Rechtsfilter unten ändern diese Übersicht nicht.",
    loading: "Prüflisten werden gezählt…",
    error:
      "Die Anzahl konnte nicht geladen werden. Öffnen Sie einen Bereich oder versuchen Sie es erneut.",
    incomplete:
      "Eine vollständige Gesamtzahl ist nicht verfügbar. Öffnen Sie die Bereiche für die vollständigen Prüflisten.",
    unavailable: "Anzahl nicht verfügbar",
    refresh: "Anzahl aktualisieren",
    checked: "Geprüft",
    empty:
      "Keine lesbaren Änderungen warten in diesen Listen auf Prüfung. Dies bestätigt keine Quellenabdeckung.",
  },
  "fr-CH": {
    title: "Changements à examiner",
    total: "Total",
    legal: "Veille juridique",
    body: "Changements non lus dans vos neuf rubriques de veille et le fil juridique, sur toutes les pages. Chaque rubrique conserve sa période Aujourd’hui. Les nombres concernent les changements enregistrés lisibles ; la disponibilité des sources figure dans chaque rubrique. Les filtres juridiques ci-dessous ne modifient pas cet aperçu.",
    loading: "Comptage des listes à examiner…",
    error:
      "Les nombres n’ont pas pu être chargés. Ouvrez une rubrique ou réessayez.",
    incomplete:
      "Le total complet est indisponible. Ouvrez les rubriques pour examiner leurs listes complètes.",
    unavailable: "Nombre indisponible",
    refresh: "Actualiser les nombres",
    checked: "Vérifié",
    empty:
      "Aucun changement enregistré lisible n’attend d’examen dans ces listes. Cela ne confirme pas la couverture des sources.",
  },
  "it-CH": {
    title: "Modifiche da esaminare",
    total: "Totale",
    legal: "Monitoraggio giuridico",
    body: "Modifiche non lette nelle nove sezioni di monitoraggio e nel flusso giuridico, su tutte le pagine. Ogni sezione mantiene il proprio intervallo Oggi. I numeri riguardano modifiche salvate leggibili; la disponibilità delle fonti è indicata nelle singole sezioni. I filtri giuridici sottostanti non cambiano questa panoramica.",
    loading: "Conteggio delle liste da esaminare…",
    error: "Impossibile caricare i conteggi. Apri una sezione o riprova.",
    incomplete:
      "Il totale completo non è disponibile. Apri le sezioni per esaminare le liste complete.",
    unavailable: "Conteggio non disponibile",
    refresh: "Aggiorna i conteggi",
    checked: "Verificato",
    empty:
      "Nessuna modifica salvata leggibile attende un esame in queste liste. Questo non conferma la copertura delle fonti.",
  },
  "rm-CH": {
    title: "Midadas da controllar",
    total: "Total",
    legal: "Monitoring giuridic",
    body: "Midadas betg legidas en Voss nov secturs da monitoring ed en il fluss giuridic, sin tut las paginas. Mintga sectur mantegna sia perioda Dad oz. Ils dumbers pertutgan midadas memorisadas legiblas; la disponibladad da las funtaunas è inditgada en mintga sectur. Ils filters giuridics sutvart na midan betg questa survista.",
    loading: "Las glistas vegnan dumbradas…",
    error:
      "Ils dumbers n’han betg pudì vegnir chargiads. Avri in sectur u empruvai anc ina giada.",
    incomplete:
      "Il total cumplet n’è betg disponibel. Avri ils secturs per controllar las glistas cumplettas.",
    unavailable: "Dumber betg disponibel",
    refresh: "Actualisar ils dumbers",
    checked: "Controllà",
    empty:
      "Naginas midadas memorisadas legiblas spetgan sin ina controlla en questas glistas. Quai na conferma betg la cuvrida da las funtaunas.",
  },
};
