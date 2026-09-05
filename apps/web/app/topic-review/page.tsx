import { Suspense } from "react";
import { Loading } from "@/components/common";
import { TopicMatchReviewPage } from "@/components/topic-match-review";

export default function TopicReviewRoute() {
  return <Suspense fallback={<Loading />}><TopicMatchReviewPage /></Suspense>;
}
