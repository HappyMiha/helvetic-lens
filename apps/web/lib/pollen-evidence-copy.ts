import type { Locale } from "./i18n";

type Copy = {
  title: string;
  retained: string;
  newer: string;
  oldSettings: string;
  withheld: string;
  reload: string;
  failed: string;
  quality: string;
  rawUnavailable: string;
};
export const pollenEvidenceCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Saved pollen evidence",
    retained:
      "This is the saved entry opened from your link. The current monitoring state is shown separately below.",
    newer:
      "Newer evidence is available. Reviewing this entry does not review later changes.",
    oldSettings: "This entry used earlier monitoring settings.",
    withheld:
      "The saved source evidence is currently unavailable under its source permissions.",
    reload: "Reload this saved entry",
    failed: "This saved entry could not be loaded. Check access and try again.",
    quality: "Recorded data quality",
    rawUnavailable: "Source-file download is not permitted for this evidence.",
  },
  "de-CH": {
    title: "Gespeicherter Pollennachweis",
    retained:
      "Dies ist der gespeicherte Eintrag aus Ihrem Link. Der aktuelle Monitoring-Stand wird unten separat angezeigt.",
    newer:
      "Neuere Nachweise sind verfügbar. Die Prüfung dieses Eintrags prüft spätere Änderungen nicht mit.",
    oldSettings: "Dieser Eintrag verwendete frühere Monitoring-Einstellungen.",
    withheld:
      "Der gespeicherte Quellennachweis ist aufgrund der Quellenberechtigungen derzeit nicht verfügbar.",
    reload: "Diesen Eintrag neu laden",
    failed:
      "Dieser Eintrag konnte nicht geladen werden. Prüfen Sie den Zugriff und versuchen Sie es erneut.",
    quality: "Gespeicherte Datenqualität",
    rawUnavailable:
      "Der Download der Quelldatei ist für diesen Nachweis nicht erlaubt.",
  },
  "fr-CH": {
    title: "Preuve pollinique enregistrée",
    retained:
      "Voici l’entrée enregistrée ouverte depuis votre lien. L’état actuel du suivi apparaît séparément ci-dessous.",
    newer:
      "Des preuves plus récentes sont disponibles. Examiner cette entrée ne marque pas les changements suivants comme examinés.",
    oldSettings: "Cette entrée utilisait des paramètres de suivi antérieurs.",
    withheld:
      "La preuve enregistrée est actuellement indisponible selon les autorisations de la source.",
    reload: "Recharger cette entrée",
    failed:
      "Cette entrée n’a pas pu être chargée. Vérifiez l’accès et réessayez.",
    quality: "Qualité enregistrée des données",
    rawUnavailable:
      "Le téléchargement du fichier source n’est pas autorisé pour cette preuve.",
  },
  "it-CH": {
    title: "Evidenza pollinica salvata",
    retained:
      "Questa è la voce salvata aperta dal collegamento. Lo stato attuale del monitoraggio è mostrato separatamente qui sotto.",
    newer:
      "Sono disponibili evidenze più recenti. Esaminare questa voce non segna come esaminate le modifiche successive.",
    oldSettings: "Questa voce usava impostazioni di monitoraggio precedenti.",
    withheld:
      "L’evidenza salvata non è attualmente disponibile secondo i permessi della fonte.",
    reload: "Ricarica questa voce",
    failed: "Impossibile caricare questa voce. Verifica l’accesso e riprova.",
    quality: "Qualità registrata dei dati",
    rawUnavailable:
      "Il download del file sorgente non è consentito per questa evidenza.",
  },
  "rm-CH": {
    title: "Cumprova da pollen memorisada",
    retained:
      "Quai è l’endataziun memorisada averta cun Voss link. Il stadi actual dal monitoring vegn mussà separadamain sutvart.",
    newer:
      "I dat cumprovas pli novas. La controlla da questa endataziun na controlla betg las midadas posteriuras.",
    oldSettings:
      "Questa endataziun duvrava parameters da monitoring anteriurs.",
    withheld:
      "La cumprova memorisada n’è actualmain betg disponibla tenor las permissiuns da la funtauna.",
    reload: "Chargiar danovamain questa endataziun",
    failed:
      "Questa endataziun n’ha betg pudì vegnir chargiada. Controllai l’access ed empruvai anc ina giada.",
    quality: "Qualitad memorisada da las datas",
    rawUnavailable:
      "Il download da la datoteca da funtauna n’è betg permess per questa cumprova.",
  },
};
