import { Suspense } from "react";
import { Loading } from "@/components/common";
import { TrademarkWatch } from "@/components/trademark-watch";
export default function TrademarkWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TrademarkWatch />
    </Suspense>
  );
}
