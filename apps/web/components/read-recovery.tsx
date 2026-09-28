"use client";

import type { Locale } from "@/lib/i18n";
import { Button } from "./ui/button";

export const readRecoveryCopy: Record<
  Locale,
  { retry: string; retrying: string; help: string }
> = {
  "en-CH": {
    retry: "Retry reading",
    retrying: "Retrying…",
    help: "The saved evidence could not be loaded. Retry to check current access.",
  },
  "de-CH": {
    retry: "Erneut laden",
    retrying: "Wird erneut geladen…",
    help: "Die gespeicherten Belege konnten nicht geladen werden. Laden Sie sie erneut, um den aktuellen Zugriff zu prüfen.",
  },
  "fr-CH": {
    retry: "Réessayer",
    retrying: "Nouvelle tentative…",
    help: "Les preuves enregistrées n’ont pas pu être chargées. Réessayez pour vérifier l’accès actuel.",
  },
  "it-CH": {
    retry: "Riprova",
    retrying: "Nuovo tentativo…",
    help: "Non è stato possibile caricare le prove salvate. Riprova per verificare l’accesso attuale.",
  },
  "rm-CH": {
    retry: "Empruvar anc ina giada",
    retrying: "Nova emprova…",
    help: "Ils mussaments memorisads na pon betg vegnir chargiads. Empruvai anc ina giada per controllar l’access actual.",
  },
};

export function ReadRecovery({
  error,
  busy,
  retry,
  locale,
}: {
  error: string;
  busy: boolean;
  retry: () => unknown;
  locale: Locale;
}) {
  if (!error) return null;
  const copy = readRecoveryCopy[locale];
  return (
    <section
      className="panel p-6 my-5"
      role="alert"
      aria-busy={busy}
      data-read-recovery
    >
      <p className="text-base leading-relaxed">{copy.help}</p>
      <p className="text-sm muted break-words my-3">{error}</p>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => {
          void retry();
        }}
      >
        {busy ? copy.retrying : copy.retry}
      </Button>
    </section>
  );
}
