import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { postPasswordForgot } from "./api";
import { AUTH_LINK_CLASS, AuthCard } from "./AuthCard";
import { AUTH_PATHS } from "./paths";
import { forgotSchema, IDENTIFIANT_MAX, type ForgotValues } from "./schemas";

const T = fr.auth;

const backToLogin = (
  <Link to={AUTH_PATHS.login} className={AUTH_LINK_CLASS}>
    {T.backToLogin}
  </Link>
);

/**
 * Demande d'un code de réinitialisation. La confirmation est toujours la même, que le compte
 * existe ou non, et quelle que soit la réponse du serveur : seule une panne réseau (requête
 * jamais arrivée) est signalée, pour permettre de réessayer.
 */
export function ForgotPasswordPage() {
  const [sentFor, setSentFor] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const confirmation = useRef<HTMLParagraphElement>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { identifiant: "" },
  });

  useEffect(() => {
    if (sentFor !== null) confirmation.current?.focus();
  }, [sentFor]);

  async function onSubmit(values: ForgotValues) {
    setFormError(null);
    try {
      await postPasswordForgot(values.identifiant);
    } catch (e) {
      if (isApiError(e) && e.status === 0) {
        setFormError(e.detail);
        return;
      }
      // Toute réponse du serveur donne la même confirmation (aucune énumération des comptes).
    }
    setSentFor(values.identifiant);
  }

  if (sentFor !== null) {
    return (
      <AuthCard title={T.forgotTitle} footer={backToLogin}>
        <p
          ref={confirmation}
          role="status"
          tabIndex={-1}
          className="rounded-md border border-border p-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          {T.forgotSent}
        </p>
        <p className="text-sm text-text-muted">{T.forgotSentHelp}</p>
        <Button asChild>
          <Link to={AUTH_PATHS.reset} state={{ identifiant: sentFor }}>
            {T.forgotEnterCode}
          </Link>
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title={T.forgotTitle} intro={T.forgotIntro} footer={backToLogin}>
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
        <Button type="submit" disabled={isSubmitting}>
          {T.forgotSubmit}
        </Button>
      </form>
    </AuthCard>
  );
}
