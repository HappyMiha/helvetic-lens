import { Suspense } from "react";
import { Loading } from "@/components/common";
import { AuctionWatch } from "@/components/auction-watch";
export default function AuctionWatchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <AuctionWatch />
    </Suspense>
  );
}
