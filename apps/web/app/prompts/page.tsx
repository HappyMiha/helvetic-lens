import { PromptSettingsPage } from "@/components/prompt-settings-page";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ scope?: string }>;
}) {
  const values = await searchParams;
  return <PromptSettingsPage platformScope={values.scope === "platform"} />;
}
