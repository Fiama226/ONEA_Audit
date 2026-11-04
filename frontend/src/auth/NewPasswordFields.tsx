import type { UseFormRegisterReturn } from "react-hook-form";
import { FormField } from "@/components/form/FormField";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { MOT_DE_PASSE_MAX } from "./schemas";

const T = fr.auth;

type Props = {
  newPassword: UseFormRegisterReturn;
  confirmation: UseFormRegisterReturn;
  newError?: string;
  confirmationError?: string;
};

/** Nouveau mot de passe et confirmation ; la règle des 12 caractères est reliée au champ. */
export function NewPasswordFields({
  newPassword,
  confirmation,
  newError,
  confirmationError,
}: Props) {
  return (
    <>
      <FormField label={T.newPassword} help={T.passwordRule} error={newError}>
        {(p) => (
          <Input
            {...p}
            type="password"
            autoComplete="new-password"
            maxLength={MOT_DE_PASSE_MAX}
            required
            {...newPassword}
          />
        )}
      </FormField>
      <FormField label={T.confirmPassword} error={confirmationError}>
        {(p) => (
          <Input
            {...p}
            type="password"
            autoComplete="new-password"
            maxLength={MOT_DE_PASSE_MAX}
            required
            {...confirmation}
          />
        )}
      </FormField>
    </>
  );
}
