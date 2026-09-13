import type { Locale } from "./i18n";

const locales: Locale[] = ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"];
const words = {
  title: [
    "Überwachung steuern",
    "Gérer la surveillance",
    "Gestisci il monitoraggio",
    "Administrar la surveglianza",
    "Manage monitoring",
  ],
  history: [
    "Statusverlauf",
    "Historique des statuts",
    "Cronologia degli stati",
    "Istorgia dals status",
    "Status history",
  ],
  prepared: [
    "Quelle und gesamter Ort sind für die gewählten Warnarten geprüft. Sie können die Überwachung starten.",
    "La source et tout le lieu sont vérifiés pour les types d’alertes choisis. Vous pouvez démarrer la surveillance.",
    "La fonte e l’intero luogo sono verificati per i tipi di avviso scelti. Puoi avviare il monitoraggio.",
    "La funtauna e l’entir lieu èn verifitgads per ils tips d’avertiment tschernids. Vus pudais avviar la surveglianza.",
    "The source and entire place are verified for the selected warning types. You can start monitoring.",
  ],
  separate: [
    "Start aktiviert die Überwachung dieses Ortes. E-Mail-Benachrichtigungen benötigen eine separate Zustimmung.",
    "Démarrer active la surveillance de ce lieu. Les notifications par e-mail nécessitent un consentement distinct.",
    "Avvia attiva il monitoraggio di questo luogo. Le notifiche e-mail richiedono un consenso separato.",
    "Avviar activescha la surveglianza da quest lieu. Avisaziuns per e-mail dovran in consentiment separà.",
    "Start activates monitoring for this place. Email notifications require separate consent.",
  ],
  source: [
    "Die Warnquelle ist nicht eingerichtet oder ihre Nutzungsrechte sind nicht bestätigt.",
    "La source d’alertes n’est pas configurée ou ses droits d’utilisation ne sont pas confirmés.",
    "La fonte di avvisi non è configurata o i diritti d’uso non sono confermati.",
    "La funtauna d’avertiments n’è betg configurada u ses dretgs d’utilisaziun n’èn betg confermads.",
    "The warning source is not configured or its usage rights are not confirmed.",
  ],
  poll: [
    "Eine aktuelle, vollständig abgeschlossene Quellenabfrage fehlt. Start bleibt gesperrt.",
    "Une interrogation récente et complète de la source manque. Le démarrage reste bloqué.",
    "Manca una verifica recente e completa della fonte. L’avvio resta bloccato.",
    "Ina consultaziun actuala e cumpletta da la funtauna manca. L’avviada resta bloccada.",
    "A recent completed source check is missing. Starting remains blocked.",
  ],
  coverage: [
    "Die Abdeckung aller gewählten Warnarten ist für diesen Ort noch nicht bestätigt.",
    "La couverture de tous les types d’alertes choisis n’est pas encore confirmée pour ce lieu.",
    "La copertura di tutti i tipi di avviso scelti non è ancora confermata per questo luogo.",
    "La cuvrida da tut ils tips d’avertiment tschernids n’è anc betg confermada per quest lieu.",
    "Coverage of every selected warning type is not yet confirmed for this place.",
  ],
  geography: [
    "Der Ort oder sein gesamter Radius liegt nicht in einem bestätigten Quellengebiet.",
    "Le lieu ou tout son rayon ne se trouve pas dans une zone de source confirmée.",
    "Il luogo o l’intero raggio non rientra in un’area confermata della fonte.",
    "Il lieu u l’entir radius na sa chatta betg en in territori confermà da la funtauna.",
    "The place or its entire radius is not within a confirmed source area.",
  ],
  stopped: [
    "Die Überwachung dieses Ortes ist pausiert. Frühere Warnungen bleiben im Verlauf.",
    "La surveillance de ce lieu est en pause. Les alertes précédentes restent dans l’historique.",
    "Il monitoraggio di questo luogo è in pausa. Gli avvisi precedenti restano nella cronologia.",
    "La surveglianza da quest lieu è en pausa. Avertiments anteriurs restan en l’istorgia.",
    "Monitoring for this place is paused. Previous warnings remain in history.",
  ],
  checked: [
    "Letzte Verarbeitung",
    "Dernier traitement",
    "Ultima elaborazione",
    "Ultima elavuraziun",
    "Last processed",
  ],
  empty: [
    "Noch keine Statusänderungen.",
    "Aucun changement de statut pour le moment.",
    "Ancora nessun cambio di stato.",
    "Anc naginas midadas da status.",
    "No status changes yet.",
  ],
};
export const hazardLifecycleCopy = Object.fromEntries(
  locales.map((locale, index) => [
    locale,
    Object.fromEntries(
      Object.entries(words).map(([key, values]) => [key, values[index]]),
    ),
  ]),
) as Record<Locale, { [K in keyof typeof words]: string }>;

export function readinessReason(locale: Locale, code: string) {
  const c = hazardLifecycleCopy[locale];
  if (code.includes("poll")) return c.poll;
  if (code.includes("coverage")) return c.coverage;
  if (code.includes("geography") || code.includes("location"))
    return c.geography;
  return c.source;
}
