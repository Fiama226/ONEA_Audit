/**
 * Valide un chemin de retour : chemin relatif de même origine uniquement.
 * Rejette "//hote", "/\hote", URL absolues, "javascript:" ; sinon renvoie "/".
 */
export function safeReturnPath(value: unknown): string {
  if (typeof value !== "string") return "/";
  // eslint-disable-next-line no-control-regex
  const cleaned = value.replace(/[\u0000-\u001f\u007f]/g, "");
  if (!cleaned.startsWith("/")) return "/";
  if (cleaned.startsWith("//") || cleaned.startsWith("/\\")) return "/";
  return cleaned;
}
