import { Suspense } from "react";
import { MonitoringSettings } from "@/components/monitoring-settings";
import { Loading } from "@/components/common";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <MonitoringSettings />
    </Suspense>
  );
}
