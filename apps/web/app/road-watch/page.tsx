import { Suspense } from "react";
import { Loading } from "@/components/common";
import { RoadWatch } from "@/components/road-watch";

export default function RoadWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RoadWatch />
    </Suspense>
  );
}
