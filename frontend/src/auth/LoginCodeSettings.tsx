import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { isApiError } from "@/api/errors";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import {
  ENVOI_COURRIEL_NON_CONFIGURE,
  postOtpDisable,
  postOtpEnable,
  postOtpEnableCode,
} from "./api";
import { codeInputProps } from "./codeInput";
import { MOT_DE_PASSE_MAX, otpSchema, type OtpValues } from "./schemas";
import { useAuth } from "./useAuth";

const T = fr.monCompte;

const confirmSchema = z.object({
  // Jamais rogné : les espaces font partie du mot de passe.
  mot_de_passe: z.string().min(1, fr.auth.currentPasswordRequired).max(MOT_DE_PASSE_MAX),
});
type ConfirmValues = z.infer<typeof confirmSchema>;

/**
 * Code de connexion par courriel de son propre compte (« Mon compte »). Activation possible
 * seulement si un courriel peut partir : sinon le serveur répond 409 et l'interrupteur est
 * désactivé avec l'explication. L'activation envoie un code de confirmation à l'adresse de
 * l'agent et n'a lieu qu'une fois ce code saisi (preuve que les courriels arrivent : sans
 * elle, une adresse fausse bloquerait l'agent à sa connexion suivante). La désactivation
 * redemande le mot de passe actuel.
 */
export function LoginCodeSettings() {
  const { me, updateMe } = useAuth();
  const switchId = useId();
  const reasonId = useId();
  const [pending, setPending] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [activating, setActivating] = useState(false);
  const reasonRef = useRef<HTMLParagraphElement>(null);
  const focusReason = useRef(false);

  // L'interrupteur devient inactif (et perd le focus) : le focus va à l'explication.
  useEffect(() => {
    if (blocked && focusReason.current) {
      focusReason.current = false;
      reasonRef.current?.focus();
    }
  }, [blocked]);

  if (!me) return null;

  const active = me.otp_connexion_actif;
  // Sans adresse, le code ne pourrait jamais arriver : l'activation est impossible d'emblée.
  const reason = active ? null : me.email === "" ? T.otpNoEmail : blocked;

  async function requestCode(): Promise<boolean> {
    setPending(true);
    setError(null);
    setNotice("");
    try {
      await postOtpEnableCode();
      return true;
    } catch (e) {
      if (isApiError(e) && e.status === 409) {
        focusReason.current = true;
        setBlocked(e.detail === ENVOI_COURRIEL_NON_CONFIGURE ? T.otpEmailNotConfigured : e.detail);
      } else {
        setError(isApiError(e) ? e.detail : fr.errors.generic);
      }
      return false;
    } finally {
      setPending(false);
    }
  }

  async function startActivation() {
    if (await requestCode()) setActivating(true);
  }

  function onToggle() {
    if (pending) return;
    if (active) {
      setNotice("");
      setError(null);
      setConfirming(true);
    } else {
      void startActivation();
    }
  }

  return (
    <section aria-labelledby={`${switchId}-title`} className="mt-8 border-t border-border pt-6">
      <h2 id={`${switchId}-title`} className="text-base font-semibold">
        {T.otpSection}
      </h2>
      <p className="mt-1 text-sm text-text-muted">{T.otpText}</p>
      <div className="mt-4 flex items-center gap-3">
        <input
          id={switchId}
          type="checkbox"
          role="switch"
          className="size-5 accent-primary disabled:cursor-not-allowed"
          checked={active}
          // Pas de `disabled` pendant l'appel : le focus resterait perdu ; onToggle l'ignore.
          disabled={reason !== null}
          aria-busy={pending || undefined}
          aria-describedby={reason ? reasonId : undefined}
          onChange={onToggle}
        />
        <label htmlFor={switchId} className="text-sm font-medium">
          {T.otpSwitch}
        </label>
        <span className="text-sm text-text-muted" aria-hidden>
          {active ? T.otpStateOn : T.otpStateOff}
        </span>
      </div>
      {/* Région annoncée rendue d'emblée : l'explication d'un refus (409) y est lue dès qu'elle arrive. */}
      <p
        id={reasonId}
        ref={reasonRef}
        tabIndex={-1}
        role="status"
        className="mt-2 text-sm text-warning-text outline-none"
      >
        {reason ?? ""}
      </p>
      {error && (
        <p role="alert" className={`mt-2 ${ALERT_CLASS}`}>
          {error}
        </p>
      )}
      <p role="status" className="mt-2 text-sm text-success-text">
        {notice}
      </p>
      <Dialog open={activating} onOpenChange={setActivating}>
        <DialogContent>
          <ActivationForm
            onResend={requestCode}
            onCancel={() => setActivating(false)}
            onDone={() => {
              updateMe({ otp_connexion_actif: true });
              setActivating(false);
              setNotice(T.otpEnabled);
            }}
          />
        </DialogContent>
      </Dialog>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DisableForm
            onCancel={() => setConfirming(false)}
            onDone={() => {
              updateMe({ otp_connexion_actif: false });
              setConfirming(false);
              setNotice(T.otpDisabled);
            }}
          />
        </DialogContent>
      </Dialog>
    </section>
  );
}

/** Code de confirmation reçu par courriel ; démonté à la fermeture. */
function ActivationForm({
  onResend,
  onCancel,
  onDone,
}: {
  onResend: () => Promise<boolean>;
  onCancel: () => void;
  onDone: () => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<OtpValues>({ resolver: zodResolver(otpSchema), defaultValues: { code: "" } });

  async function onSubmit(values: OtpValues) {
    setFormError(null);
    setResent(false);
    try {
      await postOtpEnable(values.code);
      onDone();
    } catch (e) {
      if (isApiError(e) && e.status === 400) {
        setError("code", { type: "server", message: fr.auth.otpInvalid }, { shouldFocus: true });
      } else if (isApiError(e) && e.status === 429) {
        setFormError(fr.auth.loginTooMany);
      } else {
        setFormError(isApiError(e) ? e.detail : fr.errors.generic);
      }
    }
  }

  async function resend() {
    setFormError(null);
    setResent(await onResend());
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{T.otpConfirmTitle}</DialogTitle>
        <DialogDescription>{T.otpConfirmText}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField
        label={fr.auth.otpCode}
        help={fr.auth.otpHelp}
        error={errors.code?.message}
        announceError={errors.code?.type === "server"}
      >
        {(p) => <Input {...p} required {...codeInputProps(register("code"))} />}
      </FormField>
      <p role="status" className="text-sm text-success-text">
        {resent ? T.otpConfirmResent : ""}
      </p>
      <DialogFooter>
        <Button type="button" variant="link" onClick={() => void resend()}>
          {T.otpConfirmResend}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {T.otpConfirmSubmit}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Démonté à la fermeture : le mot de passe saisi ne survit pas. */
function DisableForm({ onCancel, onDone }: { onCancel: () => void; onDone: () => void }) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ConfirmValues>({
    resolver: zodResolver(confirmSchema),
    defaultValues: { mot_de_passe: "" },
  });

  async function onSubmit(values: ConfirmValues) {
    setFormError(null);
    try {
      await postOtpDisable(values.mot_de_passe);
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["mot_de_passe"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{T.otpDisableTitle}</DialogTitle>
        <DialogDescription>{T.otpDisableText}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={fr.auth.currentPassword} error={errors.mot_de_passe?.message} announceError>
        {(p) => (
          <Input
            {...p}
            type="password"
            autoComplete="current-password"
            maxLength={MOT_DE_PASSE_MAX}
            required
            {...register("mot_de_passe")}
          />
        )}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {T.otpDisableConfirm}
        </Button>
      </DialogFooter>
    </form>
  );
}
