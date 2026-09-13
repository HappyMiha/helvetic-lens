import { Suspense } from "react";
import { Loading } from "@/components/common";
import { TenderWatch } from "@/components/tender-watch";

export default function TenderWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TenderWatch />
    </Suspense>
  );
}
