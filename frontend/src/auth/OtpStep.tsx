import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { otpSchema, type OtpValues } from "./schemas";
import { useAuth } from "./useAuth";

const T = fr.auth;

/** Second step of the login: the 6-digit code sent by email (optional, per account). */
export function OtpStep({ onBack }: { onBack: () => void }) {
  const { verifyOtp } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<OtpValues>({ resolver: zodResolver(otpSchema), defaultValues: { code: "" } });

  useEffect(() => {
    // Nouvelle étape : le focus va au champ attendu.
    setFocus("code");
  }, [setFocus]);

  async function onSubmit(values: OtpValues) {
    setFormError(null);
    try {
      await verifyOtp(values.code);
    } catch (e) {
      if (isApiError(e) && (e.status === 400 || e.status === 401)) {
        setError("code", { type: "server", message: T.otpInvalid }, { shouldFocus: true });
      } else {
        setFormError(isApiError(e) ? e.detail : fr.errors.generic);
      }
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
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
      <Button type="submit" disabled={isSubmitting}>
        {T.otpSubmit}
      </Button>
      <Button type="button" variant="link" onClick={onBack}>
        {T.otpBack}
      </Button>
    </form>
  );
}
