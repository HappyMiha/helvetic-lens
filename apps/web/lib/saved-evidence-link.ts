/** An internal link always names the complete retained version and passage. */
export function savedEvidenceHref(versionId: unknown, passageId?: unknown) {
  if (typeof versionId !== "string" || !versionId || versionId.length > 200)
    return null;
  if (passageId !== undefined && (typeof passageId !== "string" || !passageId))
    return null;
  try {
    return (
      "/evidence/" +
      encodeURIComponent(versionId) +
      (passageId === undefined
        ? ""
        : "?passage=" + encodeURIComponent(passageId as string))
    );
  } catch {
    return null;
  }
}
