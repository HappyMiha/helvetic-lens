import { Suspense } from "react";
import { Loading } from "@/components/common";
import { ImpactInboxPage } from "@/components/impact-inbox-page";

export default function ImpactRoute() {
  return (
    <Suspense fallback={<Loading text="Opening the impact inbox…" />}>
      <ImpactInboxPage />
    </Suspense>
  );
}
