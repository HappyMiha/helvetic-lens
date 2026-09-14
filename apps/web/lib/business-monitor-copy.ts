import type { Locale } from "./i18n";

export type BusinessScope = {
  visibility: "private" | "workspace";
  owner_user_id: string;
  responsible_user_id: string | null;
};
const en = {
  title: "Access and responsibility",
  private: "Private",
  defaultScope:
    "New monitors are private. You can explicitly share a saved monitor with this workspace.",
  workspace: "Workspace",
  creator: "Owner",
  responsible: "Responsible administrator",
  unassigned: "Unassigned",
  unavailable: "No longer an active administrator",
  unknown: "Former member",
  scope: "Who can access this monitor?",
  save: "Save access and responsibility",
  confirm:
    "I agree to share this profile, permitted evidence and history with this workspace.",
  effect:
    "Changing access or responsibility pauses active monitoring and revokes existing email consent. Resume separately after checking the responsible person and sources.",
  boundary:
    "Workspace administrators can manage shared monitoring; viewers can read permitted evidence. Personal email settings are not shared. Authenticated SIMAP documents require valid personal access; ownership handover revokes previous access.",
  privateEffect:
    "Restoring private access removes colleagues’ access, including through saved links. Only the current owner can change the access scope.",
  history: "Access history",
  empty: "No access changes yet",
  more: "Earlier changes",
  moreMembers: "More administrators",
  loading: "Loading access settings…",
  reload: "Reload access settings",
  failed: "Access or the monitor changed. Reload before continuing.",
  readOnly:
    "You can read this monitor. Changes require a workspace administrator.",
};
export const businessMonitorCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    title: "Zugriff und Verantwortung",
    private: "Privat",
    defaultScope:
      "Neue Überwachungen sind privat. Sie können eine gespeicherte Überwachung ausdrücklich mit diesem Arbeitsbereich teilen.",
    workspace: "Arbeitsbereich",
    creator: "Eigentümer",
    responsible: "Verantwortliche Administration",
    unassigned: "Nicht zugewiesen",
    unavailable: "Nicht mehr als Administration aktiv",
    unknown: "Ehemaliges Mitglied",
    scope: "Wer hat Zugriff auf diese Überwachung?",
    save: "Zugriff und Verantwortung speichern",
    confirm:
      "Ich stimme zu, dieses Profil, zulässige Belege und den Verlauf mit diesem Arbeitsbereich zu teilen.",
    effect:
      "Änderungen an Zugriff oder Verantwortung pausieren eine aktive Überwachung und widerrufen die bestehende E-Mail-Zustimmung. Prüfen Sie die verantwortliche Person und die Quellen vor dem separaten Fortsetzen.",
    boundary:
      "Die Administration verwaltet geteilte Überwachungen; Lesende sehen zulässige Belege. Persönliche E-Mail-Einstellungen werden nicht geteilt. Authentifizierte SIMAP-Dokumente benötigen einen gültigen persönlichen Zugang; ein Eigentümerwechsel widerruft den bisherigen Zugang.",
    privateEffect:
      "Privater Zugriff entzieht anderen Mitgliedern den Zugang, auch über gespeicherte Links. Nur die aktuell besitzende Person kann den Zugriffskreis ändern.",
    history: "Zugriffsverlauf",
    empty: "Noch keine Zugriffsänderungen",
    more: "Frühere Änderungen",
    moreMembers: "Weitere Administrierende",
    loading: "Zugriffseinstellungen werden geladen…",
    reload: "Zugriffseinstellungen neu laden",
    failed:
      "Zugriff oder Überwachung haben sich geändert. Laden Sie die Einstellungen erneut.",
    readOnly:
      "Sie können diese Überwachung lesen. Änderungen erfordern die Rolle Administration.",
  },
  "fr-CH": {
    title: "Accès et responsabilité",
    private: "Privé",
    defaultScope:
      "Les nouveaux suivis sont privés. Vous pouvez partager explicitement un suivi enregistré avec cet espace de travail.",
    workspace: "Espace de travail",
    creator: "Propriétaire",
    responsible: "Administrateur responsable",
    unassigned: "Non attribué",
    unavailable: "N’est plus administrateur actif",
    unknown: "Ancien membre",
    scope: "Qui peut accéder à ce suivi ?",
    save: "Enregistrer l’accès et la responsabilité",
    confirm:
      "J’accepte de partager ce profil, les preuves autorisées et l’historique avec cet espace de travail.",
    effect:
      "Changer l’accès ou la responsabilité suspend le suivi actif et révoque le consentement aux e-mails. Reprenez séparément après avoir vérifié la personne responsable et les sources.",
    boundary:
      "Les administrateurs gèrent les suivis partagés ; les lecteurs consultent les preuves autorisées. Les réglages personnels d’e-mail ne sont pas partagés. Les documents SIMAP authentifiés nécessitent un accès personnel valide ; le transfert de propriété révoque les accès précédents.",
    privateEffect:
      "Le retour à un accès privé retire l’accès des collègues, y compris par les liens enregistrés. Seul le propriétaire actuel peut modifier le périmètre d’accès.",
    history: "Historique des accès",
    empty: "Aucun changement d’accès",
    more: "Changements antérieurs",
    moreMembers: "Autres administrateurs",
    loading: "Chargement des accès…",
    reload: "Recharger les accès",
    failed: "L’accès ou le suivi a changé. Rechargez avant de continuer.",
    readOnly:
      "Vous pouvez consulter ce suivi. Les modifications nécessitent un administrateur.",
  },
  "it-CH": {
    title: "Accesso e responsabilità",
    private: "Privato",
    defaultScope:
      "I nuovi monitoraggi sono privati. Puoi condividere esplicitamente un monitoraggio salvato con questo spazio di lavoro.",
    workspace: "Spazio di lavoro",
    creator: "Proprietario",
    responsible: "Amministratore responsabile",
    unassigned: "Non assegnato",
    unavailable: "Non è più amministratore attivo",
    unknown: "Ex membro",
    scope: "Chi può accedere a questo monitoraggio?",
    save: "Salva accesso e responsabilità",
    confirm:
      "Acconsento a condividere questo profilo, le prove consentite e la cronologia con questo spazio di lavoro.",
    effect:
      "Cambiare accesso o responsabilità sospende il monitoraggio attivo e revoca il consenso e-mail esistente. Riprendi separatamente dopo aver verificato il responsabile e le fonti.",
    boundary:
      "Gli amministratori gestiscono i monitoraggi condivisi; i lettori consultano le prove consentite. Le impostazioni e-mail personali non sono condivise. I documenti SIMAP autenticati richiedono un accesso personale valido; il trasferimento di proprietà revoca gli accessi precedenti.",
    privateEffect:
      "Ripristinare l’accesso privato rimuove l’accesso dei colleghi, anche dai link salvati. Solo il proprietario attuale può modificare l’ambito di accesso.",
    history: "Cronologia degli accessi",
    empty: "Nessuna modifica degli accessi",
    more: "Modifiche precedenti",
    moreMembers: "Altri amministratori",
    loading: "Caricamento degli accessi…",
    reload: "Ricarica gli accessi",
    failed:
      "L’accesso o il monitoraggio è cambiato. Ricarica prima di continuare.",
    readOnly:
      "Puoi leggere questo monitoraggio. Le modifiche richiedono un amministratore.",
  },
  "rm-CH": {
    title: "Access e responsabladad",
    private: "Privat",
    defaultScope:
      "Novas surveglianzas èn privatas. Vus pudais parter explicitamain ina surveglianza memorisada cun quest spazi da lavur.",
    workspace: "Spazi da lavur",
    creator: "Possessur",
    responsible: "Administratur responsabel",
    unassigned: "Betg attribuì",
    unavailable: "Betg pli administratur activ",
    unknown: "Anteriur commember",
    scope: "Tgi po acceder a questa surveglianza?",
    save: "Memorisar access e responsabladad",
    confirm:
      "Jau sun d’accord da parter quest profil, las cumprovas permessas e l’istorgia cun quest spazi da lavur.",
    effect:
      "Midar l’access u la responsabladad metta en pausa la surveglianza activa e revocca il consentiment existent per e-mails. Cuntinuai separadamain suenter avair controllà la persuna responsabla e las funtaunas.",
    boundary:
      "Administraturs administreschan surveglianzas partidas; lecturs vesan cumprovas permessas. Ils parameters persunals d’e-mail na vegnan betg partids. Documents SIMAP autentifitgads dovran in access persunal valaivel; la surdada revoghescha ils access precedents.",
    privateEffect:
      "Restabilir l’access privat retira l’access dals collegas, era via colliaziuns memorisadas. Mo il possessur actual po midar il circul d’access.",
    history: "Istorgia da l’access",
    empty: "Anc naginas midadas d’access",
    more: "Midadas anteriuras",
    moreMembers: "Ulteriurs administraturs",
    loading: "Chargiar ils access…",
    reload: "Rechargiar ils access",
    failed:
      "L’access u la surveglianza è sa midà. Rechargiai avant da cuntinuar.",
    readOnly:
      "Vus pudais leger questa surveglianza. Midadas dovran in administratur.",
  },
};
