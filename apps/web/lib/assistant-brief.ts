import type {Locale} from "./i18n";

export const ASSISTANT_BRIEF_EVENT = "helvetic-lens:assistant-brief";
export function assistantBriefEventId(event: Event): string | null {
  const value = (event as CustomEvent<unknown>).detail;
  if (!value || typeof value !== "object" || !("eventId" in value)) return null;
  return typeof value.eventId === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.eventId) ? value.eventId : null;
}
export const assistantBriefCopy:Record<Locale,{open:string;help:string;back:string}> = {
  "en-CH": {open:"Open this brief with Marvin",help:"This is the saved, cited organization brief, not a new chat answer. Opening it does not generate or translate anything. Chat below is for navigation and conversation; it does not replace cited analysis.",back:"Return to page context"},
  "de-CH": {open:"Diese Analyse mit Marvin öffnen",help:"Dies ist die gespeicherte, belegte Organisationsanalyse, keine neue Chat-Antwort. Beim Öffnen wird nichts generiert oder übersetzt. Der Chat unten dient der Navigation und Unterhaltung; er ersetzt keine belegte Analyse.",back:"Zum Seitenkontext zurückkehren"},
  "fr-CH": {open:"Ouvrir cette analyse avec Marvin",help:"Il s’agit de l’analyse enregistrée et sourcée de l’organisation, pas d’une nouvelle réponse du chat. L’ouverture ne génère ni ne traduit rien. Le chat ci-dessous sert à la navigation et à la conversation ; il ne remplace pas une analyse sourcée.",back:"Revenir au contexte de la page"},
  "it-CH": {open:"Apri questa analisi con Marvin",help:"Questa è l’analisi salvata e documentata dell’organizzazione, non una nuova risposta della chat. L’apertura non genera né traduce nulla. La chat sotto serve alla navigazione e alla conversazione; non sostituisce un’analisi con fonti.",back:"Torna al contesto della pagina"},
  "rm-CH": {open:"Avrir questa analisa cun Marvin",help:"Quai è l’analisa memorisada e documentada da l’organisaziun, betg ina nova resposta dal chat. Avrir na generescha e na translatescha nagut. Il chat sutvart serva a la navigaziun ed a la conversaziun; el na remplazza nagina analisa cun funtaunas.",back:"Turnar al context da la pagina"},
};
