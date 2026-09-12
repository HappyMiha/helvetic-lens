import { Suspense } from "react";
import { AirWatch } from "@/components/air-watch";
import { Loading } from "@/components/common";

export default function AirWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <AirWatch />
    </Suspense>
  );
}
