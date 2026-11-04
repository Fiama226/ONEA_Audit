import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { AUTH_LINK_CLASS, AuthCard } from "./AuthCard";
import { LiveMessage } from "./LiveMessage";
import { OtpStep } from "./OtpStep";
import { AUTH_PATHS, returnPathOf, stateField } from "./paths";
import { IDENTIFIANT_MAX, loginSchema, MOT_DE_PASSE_MAX, type LoginValues } from "./schemas";
import { useAuth } from "./useAuth";

const T = fr.auth;

/** Message d'un échec de connexion : jamais le détail du serveur pour un 400 ou un 401. */
function loginErrorOf(e: unknown): { credentials: boolean; message: string } {
  if (isApiError(e) && (e.status === 400 || e.status === 401)) {
    return { credentials: true, message: T.loginFailed };
  }
  // Limitation de débit : message calme et fixe, sans le détail du serveur.
  if (isApiError(e) && e.status === 429) return { credentials: false, message: T.loginTooMany };
  return { credentials: false, message: isApiError(e) ? e.detail : fr.errors.generic };
}

export function LoginPage() {
  const { status, sessionExpired } = useAuth();
  const location = useLocation();
  const [step, setStep] = useState<"identification" | "code">("identification");
  const [identifiant, setIdentifiant] = useState("");

  if (status === "authenticated") return <Navigate to={returnPathOf(location.state)} replace />;
  if (status === "error") return <Navigate to="/erreur" replace />;
  if (status === "loading") {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {fr.common.loading}
      </p>
    );
  }

  if (step === "code") {
    return (
      <AuthCard title={T.otpTitle} intro={T.otpIntro}>
        <OtpStep onBack={() => setStep("identification")} />
      </AuthCard>
    );
  }

  const notice = stateField(location.state, "notice") === "reset" ? T.passwordResetDone : null;
  return (
    <AuthCard
      title={T.loginTitle}
      intro={T.loginPrompt}
      footer={
        <Link to={AUTH_PATHS.forgot} className={AUTH_LINK_CLASS}>
          {T.forgotLink}
        </Link>
      }
    >
      <LiveMessage
        role="alert"
        message={sessionExpired ? T.sessionExpired : null}
        className={ALERT_CLASS}
      />
      <LiveMessage
        role="status"
        message={notice && !sessionExpired ? notice : null}
        className="rounded-md border border-border p-3 text-sm"
      />
      <CredentialsForm
        defaultIdentifiant={identifiant}
        onOtp={(value) => {
          setIdentifiant(value);
          setStep("code");
        }}
      />
    </AuthCard>
  );
}

function CredentialsForm({
  defaultIdentifiant,
  onOtp,
}: {
  defaultIdentifiant: string;
  onOtp: (identifiant: string) => void;
}) {
  const { login } = useAuth();
  const failureId = useId();
  // Échec d'identification : un seul message, relié aux deux champs (on ne dit pas lequel est faux).
  const [failed, setFailed] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifiant: defaultIdentifiant, mot_de_passe: "" },
  });

  async function onSubmit(values: LoginValues) {
    setFailed(false);
    setFormError(null);
    try {
      const etape = await login(values.identifiant, values.mot_de_passe);
      if (etape === "OTP") onOtp(values.identifiant);
      // Sinon la session est ouverte : LoginPage redirige.
    } catch (e) {
      const { credentials, message } = loginErrorOf(e);
      if (credentials) {
        setValue("mot_de_passe", "");
        setFailed(true);
        setFocus("mot_de_passe");
      } else {
        setFormError(message);
      }
    }
  }

  const withFailure = (p: { "aria-invalid": boolean; "aria-describedby": string | undefined }) => ({
    "aria-invalid": p["aria-invalid"] || failed,
    "aria-describedby":
      [p["aria-describedby"], failed ? failureId : null].filter(Boolean).join(" ") || undefined,
  });

  return (
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
            {...withFailure(p)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={IDENTIFIANT_MAX}
            required
            {...register("identifiant")}
          />
        )}
      </FormField>
      <FormField label={T.password} error={errors.mot_de_passe?.message}>
        {(p) => (
          <Input
            {...p}
            {...withFailure(p)}
            type="password"
            autoComplete="current-password"
            maxLength={MOT_DE_PASSE_MAX}
            required
            {...register("mot_de_passe")}
          />
        )}
      </FormField>
      {failed && (
        // role="alert" : annoncé même quand le focus était déjà sur le mot de passe (Entrée).
        <p id={failureId} role="alert" className="text-sm text-destructive">
          {T.loginFailed}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting}>
        {T.login}
      </Button>
    </form>
  );
}
