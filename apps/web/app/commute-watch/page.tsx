import { Suspense } from "react";
import { Loading } from "@/components/common";
import { CommuteWatch } from "@/components/commute-watch";

export default function CommuteWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <CommuteWatch />
    </Suspense>
  );
}
