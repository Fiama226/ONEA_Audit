import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

/** Messages du serveur par champ (concaténés) ; vide si l'erreur n'est pas une erreur d'API. */
export function fieldErrorsOf(e: unknown): Record<string, string> {
  if (!isApiError(e)) return {};
  return Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v.join(" ")]));
}

/**
 * Message général d'une erreur : `detail` du serveur, sauf s'il ne fait que répéter le message
 * d'un champ déjà affiché sous ce champ.
 */
export function generalErrorOf(e: unknown): string | undefined {
  if (!isApiError(e)) return fr.errors.generic;
  const fields = Object.values(e.errors).flat();
  if (fields.length > 0 && fields.includes(e.detail)) return undefined;
  return e.detail || fr.errors.generic;
}
