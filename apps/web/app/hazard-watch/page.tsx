import { Suspense } from "react";
import { Loading } from "@/components/common";
import { HazardWatch } from "@/components/hazard-watch";

export default function HazardWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <HazardWatch />
    </Suspense>
  );
}
