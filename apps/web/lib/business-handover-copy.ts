import type { Locale } from "./i18n";

const en = {
  title: "Transfer ownership",
  effect:
    "The selected administrator becomes the owner and responsible person. Active monitoring pauses, email consent is cancelled and access to the previous owner’s authenticated documents is revoked. Shared decisions and evidence remain. The new owner must check sources and resume separately.",
  successor: "New owner",
  choose: "Choose another administrator",
  confirm:
    "I agree to transfer ownership and personal control to this administrator.",
  save: "Transfer this monitor",
  previous: "Previous owner",
};
export const businessHandoverCopy: Record<
  Locale,
  Record<keyof typeof en, string>
> = {
  "en-CH": en,
  "de-CH": {
    title: "Eigentum übertragen",
    effect:
      "Die gewählte Administration übernimmt Eigentum und Verantwortung. Aktive Überwachung pausiert, die E-Mail-Zustimmung wird widerrufen und der Zugriff auf authentifizierte Dokumente der bisherigen Person endet. Geteilte Entscheidungen und Belege bleiben erhalten. Die neue Person prüft die Quellen und setzt die Überwachung separat fort.",
    successor: "Neue besitzende Person",
    choose: "Andere Administration wählen",
    confirm:
      "Ich stimme zu, Eigentum und persönliche Kontrolle an diese Administration zu übertragen.",
    save: "Diese Überwachung übertragen",
    previous: "Bisherige besitzende Person",
  },
  "fr-CH": {
    title: "Transférer la propriété",
    effect:
      "L’administrateur choisi devient propriétaire et responsable. Le suivi actif est suspendu, le consentement e-mail est annulé et l’accès aux documents authentifiés de l’ancien propriétaire est révoqué. Les décisions et preuves partagées sont conservées. Le nouveau propriétaire doit vérifier les sources puis reprendre séparément.",
    successor: "Nouveau propriétaire",
    choose: "Choisir un autre administrateur",
    confirm:
      "J’accepte de transférer la propriété et le contrôle personnel à cet administrateur.",
    save: "Transférer ce suivi",
    previous: "Ancien propriétaire",
  },
  "it-CH": {
    title: "Trasferisci la proprietà",
    effect:
      "L’amministratore scelto diventa proprietario e responsabile. Il monitoraggio attivo viene sospeso, il consenso e-mail annullato e l’accesso ai documenti autenticati del precedente proprietario revocato. Le decisioni e le prove condivise restano disponibili. Il nuovo proprietario deve verificare le fonti e riprendere separatamente.",
    successor: "Nuovo proprietario",
    choose: "Scegli un altro amministratore",
    confirm:
      "Acconsento a trasferire la proprietà e il controllo personale a questo amministratore.",
    save: "Trasferisci questo monitoraggio",
    previous: "Precedente proprietario",
  },
  "rm-CH": {
    title: "Transferir la proprietad",
    effect:
      "L’administratur tschernì daventa possessur e responsabel. La surveglianza activa vegn messa en pausa, il consentiment per e-mails vegn revocà e l’access als documents autentifitgads dal possessur anteriur vegn retratg. Decisiuns e cumprovas partidas restan. Il nov possessur sto controllar las funtaunas e cuntinuar separadamain.",
    successor: "Nov possessur",
    choose: "Tscherner in auter administratur",
    confirm:
      "Jau sun d’accord da transferir la proprietad e la controlla persunala a quest administratur.",
    save: "Transferir questa surveglianza",
    previous: "Possessur anteriur",
  },
};
