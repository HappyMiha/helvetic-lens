import { Suspense } from "react";
import { RelationReprocessingPage } from "@/components/relation-reprocessing-page";

export default function Page() {
  return (
    <Suspense>
      <RelationReprocessingPage />
    </Suspense>
  );
}
