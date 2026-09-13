import type { Locale } from "./i18n";

const en = {
  title: "Profile history",
  help: "Saved search settings are immutable. Match the profile revision shown on a tender to the settings below. Opening a revision does not restore it or change monitoring.",
  any: "No restriction",
  none: "None declared",
  yes: "Yes",
  no: "No",
  changed: "Differs from the current profile",
  semantic: "Minimum semantic score",
};
export const tenderHistoryCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    title: "Profilverlauf",
    help: "Gespeicherte Suchprofile bleiben unverändert. Die Profilrevision einer Ausschreibung verweist auf diese Einstellungen. Das Öffnen einer Revision stellt sie nicht wieder her und ändert die Überwachung nicht.",
    any: "Keine Einschränkung",
    none: "Keine angegeben",
    yes: "Ja",
    no: "Nein",
    changed: "Weicht vom aktuellen Profil ab",
    semantic: "Minimaler semantischer Wert",
  },
  "fr-CH": {
    title: "Historique du profil",
    help: "Les paramètres enregistrés sont immuables. La révision du profil indiquée sur un appel d’offres correspond aux paramètres ci-dessous. Ouvrir une révision ne la restaure pas et ne modifie pas la surveillance.",
    any: "Aucune restriction",
    none: "Aucun déclaré",
    yes: "Oui",
    no: "Non",
    changed: "Diffère du profil actuel",
    semantic: "Score sémantique minimal",
  },
  "it-CH": {
    title: "Cronologia del profilo",
    help: "Le impostazioni salvate sono immutabili. La revisione del profilo indicata in un bando corrisponde alle impostazioni qui sotto. Aprire una revisione non la ripristina e non modifica il monitoraggio.",
    any: "Nessuna restrizione",
    none: "Nessuno dichiarato",
    yes: "Sì",
    no: "No",
    changed: "Diverso dal profilo attuale",
    semantic: "Punteggio semantico minimo",
  },
  "rm-CH": {
    title: "Istorgia dal profil",
    help: "Las configuraziuns memorisadas restan invariablas. La revisiun dal profil indicada tar ina publicaziun correspunda a las configuraziuns sutvart. Avrir ina revisiun na la restabilescha betg e na mida betg il monitoring.",
    any: "Nagina restricziun",
    none: "Nagin inditgà",
    yes: "Gea",
    no: "Na",
    changed: "Differenza envers il profil actual",
    semantic: "Valur semantica minimala",
  },
};
