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
import { postPasswordReset } from "./api";
import { AUTH_LINK_CLASS, AuthCard } from "./AuthCard";
import { AUTH_PATHS, stateField } from "./paths";
import { NewPasswordFields } from "./NewPasswordFields";
import { IDENTIFIANT_MAX, resetSchema, type ResetValues } from "./schemas";

const T = fr.auth;
const FIELDS = ["identifiant", "code", "nouveau_mot_de_passe"] as const;

/** Nouveau mot de passe choisi par l'agent avec le code reçu par courriel. */
export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      // Reprise de l'identifiant saisi sur « Mot de passe oublié » (état du routeur, pas l'URL).
      identifiant: stateField(location.state, "identifiant") ?? "",
      code: "",
      nouveau_mot_de_passe: "",
      confirmation: "",
    },
  });

  async function onSubmit(values: ResetValues) {
    setFormError(null);
    try {
      await postPasswordReset({
        identifiant: values.identifiant,
        code: values.code,
        nouveau_mot_de_passe: values.nouveau_mot_de_passe,
      });
      void navigate(AUTH_PATHS.login, { replace: true, state: { notice: "reset" } });
    } catch (e) {
      if (isApiError(e) && e.status === 400 && Object.keys(e.errors).length === 0) {
        // Refus uniforme (compte inconnu ou désactivé, code faux, expiré ou déjà utilisé).
        setError("code", { type: "server", message: T.otpInvalid }, { shouldFocus: true });
        return;
      }
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <AuthCard
      title={T.resetTitle}
      intro={T.resetIntro}
      footer={
        <>
          <Link to={AUTH_PATHS.forgot} className={AUTH_LINK_CLASS}>
            {T.resetNewCode}
          </Link>
          <Link to={AUTH_PATHS.login} className={AUTH_LINK_CLASS}>
            {T.backToLogin}
          </Link>
        </>
      }
    >
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
        {formError && (
          <p role="alert" className={ALERT_CLASS}>
            {formError}
          </p>
        )}
        <FormField label={T.identifiant} error={errors.identifiant?.message}>
          {(p) => (
            <Input
              {...p}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={IDENTIFIANT_MAX}
              required
              {...register("identifiant")}
            />
          )}
        </FormField>
        <FormField
          label={T.otpCode}
          help={T.otpHelp}
          error={errors.code?.message}
          announceError={errors.code?.type === "server"}
        >
          {(p) => (
            <Input
              {...p}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              {...register("code")}
            />
          )}
        </FormField>
        <NewPasswordFields
          newPassword={register("nouveau_mot_de_passe")}
          confirmation={register("confirmation")}
          newError={errors.nouveau_mot_de_passe?.message}
          confirmationError={errors.confirmation?.message}
        />
        <Button type="submit" disabled={isSubmitting}>
          {T.resetSubmit}
        </Button>
      </form>
    </AuthCard>
  );
}
