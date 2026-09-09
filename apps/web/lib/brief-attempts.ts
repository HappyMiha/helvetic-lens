import type { Locale } from "./i18n";
export type BriefAttempts = {
  items: Array<{
    number: number;
    status: string;
    started_at: string;
    finished_at: string | null;
    error_code: string | null;
    measurement: {
      http_attempts_started: number;
      elapsed_run_ms: number;
      measured_input_requests: number;
      measured_input_tokens: number | null;
      reported_output_requests: number;
      reported_output_tokens: number | null;
      observed_queue_requests: number;
      observed_queue_ms: number | null;
    } | null;
  }>;
};
export const briefAttemptCopy: Record<
  Locale,
  {
    title: string;
    help: string;
    empty: string;
    http: string;
    input: string;
    output: string;
    queue: string;
    elapsed: string;
    coverage: string;
    error: string;
  }
> = {
  "en-CH": {
    title: "Attempt history and usage",
    help: "Each new generation attempt is kept separately. Request starts are not confirmed billable calls. Token and queue totals cover only the observed requests shown below. Older attempts are not reconstructed; a process crash or missing provider usage may leave unknown measurements.",
    empty: "No recorded attempts. Earlier runs were not backfilled.",
    http: "HTTP attempts started",
    input: "Measured input tokens",
    output: "Provider-reported output tokens",
    queue: "Observed provider queue time (ms)",
    elapsed: "Elapsed run time (ms)",
    coverage: "Observed requests / started requests",
    error: "Failure category",
  },
  "de-CH": {
    title: "Versuchsverlauf und Nutzung",
    help: "Jeder neue Generierungsversuch wird separat gespeichert. Gestartete Anfragen sind keine bestätigten abrechenbaren Aufrufe. Token- und Wartesummen umfassen nur die unten angegebenen beobachteten Anfragen. Frühere Versuche werden nicht rekonstruiert; nach Abstürzen oder ohne Anbieterangaben können Messwerte fehlen.",
    empty: "Keine erfassten Versuche. Frühere Läufe wurden nicht nachgetragen.",
    http: "Gestartete HTTP-Versuche",
    input: "Gemessene Eingabetokens",
    output: "Vom Anbieter gemeldete Ausgabetokens",
    queue: "Beobachtete Anbieterwartezeit (ms)",
    elapsed: "Verstrichene Laufzeit (ms)",
    coverage: "Beobachtete / gestartete Anfragen",
    error: "Fehlerkategorie",
  },
  "fr-CH": {
    title: "Historique des tentatives et usage",
    help: "Chaque nouvelle tentative est conservée séparément. Une requête lancée n’est pas un appel facturable confirmé. Les totaux de jetons et d’attente couvrent uniquement les requêtes observées ci-dessous. Les anciennes tentatives ne sont pas reconstruites ; un arrêt du processus ou l’absence de données du fournisseur peut laisser des mesures inconnues.",
    empty:
      "Aucune tentative enregistrée. Les exécutions antérieures n’ont pas été reconstituées.",
    http: "Tentatives HTTP lancées",
    input: "Jetons d’entrée mesurés",
    output: "Jetons de sortie déclarés par le fournisseur",
    queue: "Attente observée chez le fournisseur (ms)",
    elapsed: "Durée écoulée (ms)",
    coverage: "Requêtes observées / lancées",
    error: "Catégorie d’échec",
  },
  "it-CH": {
    title: "Cronologia dei tentativi e utilizzo",
    help: "Ogni nuovo tentativo di generazione viene conservato separatamente. Le richieste avviate non sono chiamate fatturabili confermate. I totali di token e attesa coprono solo le richieste osservate sotto. I tentativi precedenti non vengono ricostruiti; arresti o dati mancanti del fornitore possono lasciare misurazioni sconosciute.",
    empty:
      "Nessun tentativo registrato. Le esecuzioni precedenti non sono state ricostruite.",
    http: "Tentativi HTTP avviati",
    input: "Token di ingresso misurati",
    output: "Token di uscita dichiarati dal fornitore",
    queue: "Attesa osservata del fornitore (ms)",
    elapsed: "Tempo trascorso (ms)",
    coverage: "Richieste osservate / avviate",
    error: "Categoria di errore",
  },
  "rm-CH": {
    title: "Cronologia da las emprovas ed utilisaziun",
    help: "Mintga nova emprova da generaziun vegn conservada separadamain. Dumondas lantschadas n’èn betg clamadas pajablas confermadas. Ils totals da tokens e da spetga cumpiglian mo las dumondas observadas sutvart. Emprovas pli veglias na vegnan betg reconstruidas; interrupziuns u datas mancantas dal furnitur pon laschar mesiraziuns nunenconuschentas.",
    empty:
      "Naginas emprovas registradas. Lavurs anteriuras n’èn betg vegnidas reconstruidas.",
    http: "Emprovas HTTP lantschadas",
    input: "Tokens d’entrada mesirads",
    output: "Tokens da sortida inditgads dal furnitur",
    queue: "Temp da spetga observà tar il furnitur (ms)",
    elapsed: "Temp da lavur passà (ms)",
    coverage: "Dumondas observadas / lantschadas",
    error: "Categoria d’errur",
  },
};
