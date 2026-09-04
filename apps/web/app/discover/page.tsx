import { Suspense } from "react";
import { Loading } from "@/components/common";
import { RegistryPage } from "@/components/registry-page";

export default function DiscoverRoute() {
  return (
    <Suspense fallback={<Loading />}>
      <RegistryPage defaultView="events" />
    </Suspense>
  );
}
