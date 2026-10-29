import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

/**
 * Pose les erreurs de validation du serveur ({detail, errors}) sur les champs connus.
 * Retourne le message général à afficher en alerte (détail, ou erreurs sans champ), sinon null.
 */
export function applyApiErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!isApiError(error)) return fr.errors.generic;
  let matched = false;
  const leftovers: string[] = [];
  let first = true;
  for (const [field, messages] of Object.entries(error.errors)) {
    if ((fields as readonly string[]).includes(field)) {
      setError(
        field as Path<T>,
        { type: "server", message: messages.join(" ") },
        { shouldFocus: first },
      );
      first = false;
      matched = true;
    } else {
      leftovers.push(...messages);
    }
  }
  if (leftovers.length > 0) return leftovers.join(" ");
  return matched ? null : error.detail;
}
