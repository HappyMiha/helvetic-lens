import type { Locale } from "./i18n";

type Copy = {
  title: string;
  profiles: Record<string, string>;
  suites: Record<string, string>;
  noTests: string;
  skipped: string;
  separateIntegration: string;
  steps: Record<string, string>;
};

export const deploymentTestsCopy: Record<Locale, Copy> = {
  "en-CH": {
    title: "Release checks",
    profiles: {
      standard: "Standard release",
      full: "Full regression",
      hotfix: "Emergency hotfix — tests skipped",
    },
    suites: {
      smoke: "Platform smoke",
      functional: "Functional",
      integration: "Integration",
      full: "Complete API suite",
    },
    noTests:
      "API and web tests were skipped. Build, backup and activation checks still apply.",
    skipped: "Skipped",
    separateIntegration:
      "Integration regression is separate from the standard release. Use the full profile to include it.",
    steps: {
      api_tests: "API tests",
      web_tests: "Web tests",
      integration_tests: "Integration tests",
    },
  },
  "de-CH": {
    title: "Release-Prüfungen",
    profiles: {
      standard: "Standard-Release",
      full: "Vollständige Regression",
      hotfix: "Notfall-Hotfix — Tests übersprungen",
    },
    suites: {
      smoke: "Plattform-Grundprüfung",
      functional: "Funktionstests",
      integration: "Integrationstests",
      full: "Vollständige API-Tests",
    },
    noTests:
      "API- und Webtests wurden übersprungen. Build, Sicherung und Aktivierungsprüfungen bleiben erforderlich.",
    skipped: "Übersprungen",
    separateIntegration:
      "Integrationstests sind vom Standard-Release getrennt. Das vollständige Profil schliesst sie ein.",
    steps: {
      api_tests: "API-Tests",
      web_tests: "Webtests",
      integration_tests: "Integrationstests",
    },
  },
  "fr-CH": {
    title: "Vérifications de la version",
    profiles: {
      standard: "Version standard",
      full: "Régression complète",
      hotfix: "Correctif d’urgence — tests ignorés",
    },
    suites: {
      smoke: "Fonctionnement de la plateforme",
      functional: "Tests fonctionnels",
      integration: "Tests d’intégration",
      full: "Suite API complète",
    },
    noTests:
      "Les tests API et web ont été ignorés. La compilation, la sauvegarde et les vérifications d’activation restent requises.",
    skipped: "Ignoré",
    separateIntegration:
      "Les tests d’intégration sont séparés de la version standard. Le profil complet les inclut.",
    steps: {
      api_tests: "Tests API",
      web_tests: "Tests web",
      integration_tests: "Tests d’intégration",
    },
  },
  "it-CH": {
    title: "Verifiche della versione",
    profiles: {
      standard: "Versione standard",
      full: "Regressione completa",
      hotfix: "Correzione urgente — test saltati",
    },
    suites: {
      smoke: "Funzionamento della piattaforma",
      functional: "Test funzionali",
      integration: "Test d’integrazione",
      full: "Suite API completa",
    },
    noTests:
      "I test API e web sono stati saltati. Compilazione, backup e verifiche di attivazione restano obbligatori.",
    skipped: "Saltato",
    separateIntegration:
      "I test d’integrazione sono separati dalla versione standard. Il profilo completo li include.",
    steps: {
      api_tests: "Test API",
      web_tests: "Test web",
      integration_tests: "Test d’integrazione",
    },
  },
  "rm-CH": {
    title: "Controllas da la versiun",
    profiles: {
      standard: "Versiun standard",
      full: "Regressiun cumpletta",
      hotfix: "Correctura urgenta — tests omess",
    },
    suites: {
      smoke: "Funcziunament da la plattafurma",
      functional: "Tests funcziunals",
      integration: "Tests d’integraziun",
      full: "Tut ils tests API",
    },
    noTests:
      "Ils tests API e web èn vegnids omess. Compilaziun, copia da segirezza e controllas d’activaziun restan necessarias.",
    skipped: "Omess",
    separateIntegration:
      "Ils tests d’integraziun èn separads da la versiun standard. Il profil cumplet als includa.",
    steps: {
      api_tests: "Tests API",
      web_tests: "Tests web",
      integration_tests: "Tests d’integraziun",
    },
  },
};
