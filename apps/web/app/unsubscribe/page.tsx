"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, MailX } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function Unsubscribe() {
  const { t } = useI18n();
  const started = useRef(false);
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [error, setError] = useState("");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token =
      new URLSearchParams(window.location.search).get("token") || "";
    api("/digests/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then(() => setState("done"))
      .catch((cause) => {
        setError(errorText(cause));
        setState("error");
      });
  }, []);
  return (
    <main className="min-h-screen grid place-items-center bg-[#f7f7f3] p-6">
      <section className="panel p-8 max-w-lg text-center">
        {state === "working" ? (
          <Loader2 className="animate-spin mx-auto" />
        ) : state === "done" ? (
          <CheckCircle2 className="mx-auto text-primary" />
        ) : (
          <MailX className="mx-auto text-red-600" />
        )}
        <h1 className="mt-4">
          {state === "done"
            ? t("unsubscribe.done")
            : state === "error"
              ? t("unsubscribe.error")
              : t("unsubscribe.working")}
        </h1>
        <p className="muted">
          {state === "error"
            ? error
            : t(
                state === "done"
                  ? "unsubscribe.doneBody"
                  : "unsubscribe.workingBody",
              )}
        </p>
        <Link href="/digests">{t("unsubscribe.open")}</Link>
      </section>
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Unsubscribe />
    </Suspense>
  );
}
