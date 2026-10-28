import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

/**
 * Pose les erreurs de champ renvoyées par le serveur ({detail, errors}) sur le formulaire et
 * renvoie le message général (détail, ou erreurs sur des champs inconnus), à afficher en alerte.
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly string[],
): string {
  if (!isApiError(error)) return fr.errors.generic;
  let general = "";
  let mapped = false;
  for (const [field, messages] of Object.entries(error.errors)) {
    if (fields.includes(field)) {
      setError(field as Path<T>, { type: "server", message: messages.join(" ") });
      mapped = true;
    } else {
      general += `${messages.join(" ")} `;
    }
  }
  if (general.trim()) return general.trim();
  return mapped ? "" : error.detail;
}
