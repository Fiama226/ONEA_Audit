import type { ChangeEvent } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";
import { CODE_SAISIE_MAX, digitsOnly } from "./schemas";

/**
 * Propriétés du champ du code à 6 chiffres (connexion, réinitialisation). Le collage d'un code
 * avec espaces ou retour à la ligne fonctionne (WCAG 2.2, 3.3.8) : la longueur saisissable
 * dépasse 6 et seuls les chiffres sont gardés, dans le champ comme à l'envoi.
 */
export function codeInputProps(field: UseFormRegisterReturn) {
  return {
    ...field,
    inputMode: "numeric" as const,
    autoComplete: "one-time-code",
    maxLength: CODE_SAISIE_MAX,
    onChange: (event: ChangeEvent<HTMLInputElement>) => {
      event.target.value = digitsOnly(event.target.value);
      return field.onChange(event);
    },
  };
}
