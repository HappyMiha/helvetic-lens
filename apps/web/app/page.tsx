import { Suspense } from "react";
import { Loading } from "@/components/common";
import { InterestFeedPage } from "@/components/interest-feed-page";

export default function Home() {
  return <Suspense fallback={<Loading />}><InterestFeedPage /></Suspense>;
}
