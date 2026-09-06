import { MonitoringTopicsPage } from "@/components/monitoring-topics-page";

export default async function TopicsRoute({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const kind = typeof params.from === "string" ? params.from : "";
  const id = typeof params.record === "string" ? params.record : "";
  const messageId = typeof params.message === "string" ? params.message : undefined;
  return (
    <MonitoringTopicsPage context={kind || id ? { kind, id, messageId } : undefined} />
  );
}
