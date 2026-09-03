import { Suspense } from "react";
import { Loading } from "@/components/common";
import { RegistryPage } from "@/components/registry-page";

export default function RegistryRoute() {
  return (
    <Suspense fallback={<Loading text="Loading the saved registry…" />}>
      <RegistryPage />
    </Suspense>
  );
}
