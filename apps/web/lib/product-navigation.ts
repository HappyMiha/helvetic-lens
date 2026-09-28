export type ProductName = "pharma" | "legal" | "platform";
export const productDestinations = [
  { id: "pharma", name: "Pharma", href: "https://pharma.helveticlens.ch/" },
  { id: "legal", name: "Legal", href: "https://legal.helveticlens.ch/" },
  { id: "platform", name: "Monitoring", href: "https://helveticlens.ch/" },
] as const;
export const productNavigationCopy = {
  "en-CH": {
    title: "Helvetic Lens products",
    current: "You are here",
    opens: "Opens in a new tab",
    note: "Other products open in a new tab. Your work stays here.",
  },
  "de-CH": {
    title: "Helvetic Lens Produkte",
    current: "Sie sind hier",
    opens: "Öffnet in einem neuen Tab",
    note: "Andere Produkte öffnen in einem neuen Tab. Ihre Arbeit bleibt hier.",
  },
  "fr-CH": {
    title: "Produits Helvetic Lens",
    current: "Vous êtes ici",
    opens: "Ouvre un nouvel onglet",
    note: "Les autres produits s’ouvrent dans un nouvel onglet. Votre travail reste ici.",
  },
  "it-CH": {
    title: "Prodotti Helvetic Lens",
    current: "Sei qui",
    opens: "Si apre in una nuova scheda",
    note: "Gli altri prodotti si aprono in una nuova scheda. Il tuo lavoro rimane qui.",
  },
  "rm-CH": {
    title: "Products Helvetic Lens",
    current: "Vus essas qua",
    opens: "Avra en in nov tab",
    note: "Ils auters products s’avran en in nov tab. Vossa lavur resta qua.",
  },
};
