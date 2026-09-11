import type { Locale } from "./i18n";

type Copy = {
  create: string;
  intro: string;
  allergens: string;
  numeric: string;
  threshold: string;
  rapid: string;
  preview: string;
  checked: string;
  save: string;
  saved: string;
  view: string;
  cancel: string;
  invalid: string;
  failed: string;
  uncertain: string;
  discard: string;
  select: string;
  busy: string;
};
export const pollenCreateCopy: Record<Locale, Copy> = {
  "en-CH": {
    create: "New Pollen Watch draft",
    intro:
      "Save private settings for later. This does not verify station coverage, start monitoring or enable email. Numeric values use number/m3.",
    allergens: "Choose allergens",
    numeric: "Add a numeric rule",
    threshold: "Threshold with reset",
    rapid: "Rapid increase",
    preview: "Check settings",
    checked:
      "Settings checked. Live coverage remains unverified; no observations or forecasts were loaded.",
    save: "Save private draft",
    saved: "Private draft saved. Monitoring has not started.",
    view: "View saved draft",
    cancel: "Discard new draft",
    invalid:
      "Check the station, timezone and numeric rules. Reset must be below the trigger; rapid windows must be 1–24 hours.",
    failed: "The settings could not be checked. Try again.",
    uncertain:
      "The save could not be confirmed. Settings are locked so Retry uses the same request and cannot create a second draft. Use Save again to confirm the result.",
    discard:
      "Leave this unfinished draft? Unsaved settings will be lost. An unconfirmed save may already exist; retry it before leaving to avoid creating a duplicate later.",
    select: "Choose at least one allergen.",
    busy: "Working…",
  },
  "de-CH": {
    create: "Neuer Pollen-Watch-Entwurf",
    intro:
      "Private Einstellungen für später speichern. Dies bestätigt keine Stationsabdeckung, startet keine Überwachung und aktiviert keine E-Mails. Zahlenwerte verwenden number/m3.",
    allergens: "Allergene auswählen",
    numeric: "Numerische Regel hinzufügen",
    threshold: "Schwelle mit Rücksetzung",
    rapid: "Rascher Anstieg",
    preview: "Einstellungen prüfen",
    checked:
      "Einstellungen geprüft. Die Live-Abdeckung bleibt ungeprüft; keine Beobachtungen oder Prognosen wurden geladen.",
    save: "Privaten Entwurf speichern",
    saved:
      "Privater Entwurf gespeichert. Die Überwachung wurde nicht gestartet.",
    view: "Gespeicherten Entwurf öffnen",
    cancel: "Neuen Entwurf verwerfen",
    invalid:
      "Prüfen Sie Station, Zeitzone und Zahlenregeln. Die Rücksetzschwelle muss unter der Auslöseschwelle liegen; Anstiegsfenster müssen 1–24 Stunden betragen.",
    failed:
      "Die Einstellungen konnten nicht geprüft werden. Versuchen Sie es erneut.",
    uncertain:
      "Das Speichern konnte nicht bestätigt werden. Die Einstellungen sind gesperrt, damit ein erneuter Versuch dieselbe Anfrage verwendet und keinen zweiten Entwurf erzeugt. Klicken Sie erneut auf Speichern.",
    discard:
      "Diesen unfertigen Entwurf verlassen? Ungespeicherte Einstellungen gehen verloren. Ein unbestätigter Entwurf kann bereits gespeichert sein; wiederholen Sie das Speichern vor dem Verlassen, um spätere Duplikate zu vermeiden.",
    select: "Wählen Sie mindestens ein Allergen.",
    busy: "Wird bearbeitet…",
  },
  "fr-CH": {
    create: "Nouveau brouillon Pollen Watch",
    intro:
      "Enregistrez des paramètres privés pour plus tard. Cela ne vérifie pas la couverture de la station, ne démarre pas la surveillance et n’active pas les e-mails. Les valeurs utilisent number/m3.",
    allergens: "Choisir les allergènes",
    numeric: "Ajouter une règle numérique",
    threshold: "Seuil avec réinitialisation",
    rapid: "Augmentation rapide",
    preview: "Vérifier les paramètres",
    checked:
      "Paramètres vérifiés. La couverture en direct reste non vérifiée ; aucune observation ni prévision n’a été chargée.",
    save: "Enregistrer le brouillon privé",
    saved: "Brouillon privé enregistré. La surveillance n’a pas démarré.",
    view: "Voir le brouillon enregistré",
    cancel: "Abandonner le nouveau brouillon",
    invalid:
      "Vérifiez la station, le fuseau horaire et les règles. Le seuil de réinitialisation doit être inférieur au seuil de déclenchement ; les fenêtres doivent durer 1 à 24 heures.",
    failed: "Impossible de vérifier les paramètres. Réessayez.",
    uncertain:
      "L’enregistrement n’a pas pu être confirmé. Les paramètres sont verrouillés pour réutiliser la même requête sans créer un second brouillon. Cliquez à nouveau sur Enregistrer.",
    discard:
      "Quitter ce brouillon inachevé ? Les paramètres non enregistrés seront perdus. Un enregistrement non confirmé peut déjà exister ; réessayez avant de quitter pour éviter un doublon ultérieur.",
    select: "Choisissez au moins un allergène.",
    busy: "Traitement…",
  },
  "it-CH": {
    create: "Nuova bozza Pollen Watch",
    intro:
      "Salvate impostazioni private per dopo. Questo non verifica la copertura della stazione, non avvia il monitoraggio e non abilita le e-mail. I valori usano number/m3.",
    allergens: "Scegliere gli allergeni",
    numeric: "Aggiungere una regola numerica",
    threshold: "Soglia con ripristino",
    rapid: "Aumento rapido",
    preview: "Verifica impostazioni",
    checked:
      "Impostazioni verificate. La copertura dal vivo resta non verificata; nessuna osservazione o previsione è stata caricata.",
    save: "Salva bozza privata",
    saved: "Bozza privata salvata. Il monitoraggio non è stato avviato.",
    view: "Visualizza bozza salvata",
    cancel: "Scarta la nuova bozza",
    invalid:
      "Controllate stazione, fuso orario e regole. La soglia di ripristino deve essere inferiore alla soglia di attivazione; le finestre devono durare da 1 a 24 ore.",
    failed: "Impossibile verificare le impostazioni. Riprovate.",
    uncertain:
      "Il salvataggio non è stato confermato. Le impostazioni sono bloccate per riutilizzare la stessa richiesta senza creare una seconda bozza. Premete nuovamente Salva.",
    discard:
      "Lasciare questa bozza incompleta? Le impostazioni non salvate andranno perse. Un salvataggio non confermato potrebbe già esistere; riprovate prima di uscire per evitare duplicati successivi.",
    select: "Scegliete almeno un allergene.",
    busy: "Elaborazione…",
  },
  "rm-CH": {
    create: "Nov sboz Pollen Watch",
    intro:
      "Memorisar parameters privats per pli tard. Quai na verifitgescha betg la cuvrida da la staziun, na cumenza nagina surveglianza e n’activescha nagins e-mails. Las valurs dovran number/m3.",
    allergens: "Tscherner allergens",
    numeric: "Agiuntar ina regla numerica",
    threshold: "Sava cun reinizialisaziun",
    rapid: "Augment rapid",
    preview: "Verifitgar ils parameters",
    checked:
      "Parameters verifitgads. La cuvrida actuala resta nunverifitgada; naginas observaziuns u prognosas èn vegnidas chargiadas.",
    save: "Memorisar il sboz privat",
    saved: "Sboz privat memorisà. La surveglianza n’è betg cumenzada.",
    view: "Vesair il sboz memorisà",
    cancel: "Sbittar il nov sboz",
    invalid:
      "Controllescha la staziun, la zona d’urari e las reglas. La sava da reinizialisaziun sto esser sut la sava d’activaziun; las fanestras ston durar 1–24 uras.",
    failed:
      "Ils parameters n’han betg pudì vegnir verifitgads. Emprova danovamain.",
    uncertain:
      "La memorisaziun n’ha betg pudì vegnir confermada. Ils parameters èn bloccads per reutilisar la medema dumonda senza crear in segund sboz. Clicca anc ina giada sin Memorisar.",
    discard:
      "Bandunar quest sboz nunfinì? Parameters betg memorisads van a perder. Ina memorisaziun nunconfermada po gia exister; emprova danovamain avant da bandunar per evitar duplicates pli tard.",
    select: "Tscherna almain in allergen.",
    busy: "Elavurar…",
  },
};
