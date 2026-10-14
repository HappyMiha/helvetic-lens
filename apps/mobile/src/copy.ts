// Copy for the few native screens; the site itself handles its own languages.
const messages = {
  en: {
    offlineTitle: "No connection",
    offlineBody: "Helvetic Lens needs the internet to load your workspace. Check your connection and try again.",
    errorTitle: "Helvetic Lens is not reachable",
    errorBody: "The site did not respond. Try again in a moment.",
    retry: "Try again",
  },
  de: {
    offlineTitle: "Keine Verbindung",
    offlineBody: "Helvetic Lens braucht eine Internetverbindung, um Ihren Arbeitsbereich zu laden. Prüfen Sie die Verbindung und versuchen Sie es erneut.",
    errorTitle: "Helvetic Lens ist nicht erreichbar",
    errorBody: "Die Website hat nicht geantwortet. Versuchen Sie es gleich noch einmal.",
    retry: "Erneut versuchen",
  },
  fr: {
    offlineTitle: "Pas de connexion",
    offlineBody: "Helvetic Lens a besoin d'Internet pour charger votre espace de travail. Vérifiez votre connexion et réessayez.",
    errorTitle: "Helvetic Lens est inaccessible",
    errorBody: "Le site n'a pas répondu. Réessayez dans un instant.",
    retry: "Réessayer",
  },
  it: {
    offlineTitle: "Nessuna connessione",
    offlineBody: "Helvetic Lens ha bisogno di Internet per caricare il tuo spazio di lavoro. Controlla la connessione e riprova.",
    errorTitle: "Helvetic Lens non è raggiungibile",
    errorBody: "Il sito non ha risposto. Riprova tra un momento.",
    retry: "Riprova",
  },
} as const;

export type Copy = (typeof messages)[keyof typeof messages];

export function copyFor(locale: string | undefined): Copy {
  const language = (locale ?? "en").slice(0, 2).toLowerCase();
  return language in messages ? messages[language as keyof typeof messages] : messages.en;
}
