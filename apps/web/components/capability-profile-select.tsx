"use client";

import { localeNames, useI18n } from "@/lib/i18n";
import type { ApertusSettings } from "@/lib/types";
import { capabilityCopy } from "@/lib/capability-copy";

export function CapabilityProfileSelect({
  settings,
  value,
  onChange,
}: {
  settings: ApertusSettings;
  value: string;
  onChange: (value: string) => void;
}) {
  const { locale } = useI18n();
  const copy = capabilityCopy[locale];
  const profiles = settings.explanation_profiles ?? [];
  const selected = profiles.find((profile) => profile.id === value);
  return (
    <div
      className="min-w-0 rounded-lg border p-4 text-sm"
      data-capability-profile
    >
      <label htmlFor="explanation-profile">{copy.title}</label>
      <select
        id="explanation-profile"
        className="w-full min-w-0"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby="explanation-profile-help"
      >
        <option value="">{copy.none}</option>
        {value && !selected && (
          <option value={value}>
            {copy.unavailable}: {value}
          </option>
        )}
        {profiles.map((profile) => (
          <option key={profile.id} value={profile.id}>
            {profile.id} · {copy[profile.status]} · {profile.revision}
          </option>
        ))}
      </select>
      <p id="explanation-profile-help" className="field-help !mb-0">
        {copy.help}
      </p>
      {settings.explanation_registry_valid === false ? (
        <p className="mt-2 font-medium" role="status">
          {copy.invalid}
        </p>
      ) : profiles.length === 0 ? (
        <p className="mt-2">{copy.empty}</p>
      ) : null}
      {selected && (
        <div className="mt-2 break-words" data-capability-scopes>
          <p>
            {selected.model_id} · {copy[selected.status]}
          </p>
          <ul className="mt-1 list-disc pl-5">
            {selected.scopes.map((scope) => (
              <li key={scope.task + scope.locale}>
                {copy[scope.task]} · {localeNames[scope.locale]}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
