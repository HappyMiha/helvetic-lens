import { RiverWatch } from "@/components/river-watch";
import { Suspense } from "react";
import { Loading } from "@/components/common";

export default function RiverWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RiverWatch />
    </Suspense>
  );
}
