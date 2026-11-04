import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { AUTH_LINK_CLASS, AuthCard } from "./AuthCard";
import { NewPasswordFields } from "./NewPasswordFields";
import { PASSWORD_CHANGED_NOTICE, returnPathOf } from "./paths";
import { changeSchema, MOT_DE_PASSE_MAX, type ChangeValues } from "./schemas";
import { useAuth } from "./useAuth";

const T = fr.auth;
const FIELDS = ["ancien", "nouveau"] as const;

/**
 * Changement de son mot de passe : imposé après un mot de passe temporaire (RequireAuth y
 * redirige), ou volontaire. Les autres sessions de l'agent sont fermées par le serveur.
 */
export function ChangePasswordPage() {
  const { etape, changePassword, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const forced = etape === "CHANGER_MOT_DE_PASSE";
  const retour = returnPathOf(location.state);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangeValues>({
    resolver: zodResolver(changeSchema),
    defaultValues: { ancien: "", nouveau: "", confirmation: "" },
  });

  async function onSubmit(values: ChangeValues) {
    setFormError(null);
    try {
      await changePassword(values.ancien, values.nouveau);
      // Confirmation affichée par la coque sur la page d'arrivée (message d'état, WCAG 4.1.3).
      void navigate(retour, { replace: true, state: { notice: PASSWORD_CHANGED_NOTICE } });
    } catch (e) {
      // Limitation de débit : texte fixe, comme à la connexion (pas le détail du serveur).
      if (isApiError(e) && e.status === 429) setFormError(T.loginTooMany);
      else setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <AuthCard
      title={T.changeTitle}
      intro={forced ? T.changeForcedIntro : T.changeIntro}
      footer={
        forced ? (
          <Button type="button" variant="link" onClick={() => void logout()}>
            {T.logout}
          </Button>
        ) : (
          <Link to={retour} className={AUTH_LINK_CLASS}>
            {T.changeCancel}
          </Link>
        )
      }
    >
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
        {formError && (
          <p role="alert" className={ALERT_CLASS}>
            {formError}
          </p>
        )}
        <FormField
          label={T.currentPassword}
          help={forced ? T.currentPasswordTemporaryHelp : undefined}
          error={errors.ancien?.message}
          announceError={errors.ancien?.type === "server"}
        >
          {(p) => (
            <Input
              {...p}
              type="password"
              autoComplete="current-password"
              maxLength={MOT_DE_PASSE_MAX}
              required
              {...register("ancien")}
            />
          )}
        </FormField>
        <NewPasswordFields
          newPassword={register("nouveau")}
          confirmation={register("confirmation")}
          newError={errors.nouveau?.message}
          confirmationError={errors.confirmation?.message}
        />
        <Button type="submit" disabled={isSubmitting}>
          {T.changeSubmit}
        </Button>
      </form>
    </AuthCard>
  );
}
