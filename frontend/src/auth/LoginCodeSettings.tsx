import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
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
import { ENVOI_COURRIEL_NON_CONFIGURE, postOtpDisable, postOtpEnable } from "./api";
import { MOT_DE_PASSE_MAX } from "./schemas";
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
 * désactivé avec l'explication. La désactivation redemande le mot de passe actuel.
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
  if (!me) return null;

  const active = me.otp_connexion_actif;
  // Sans adresse, le code ne pourrait jamais arriver : l'activation est impossible d'emblée.
  const reason = active ? null : me.email === "" ? T.otpNoEmail : blocked;

  async function enable() {
    setPending(true);
    setError(null);
    setNotice("");
    try {
      const etat = await postOtpEnable();
      updateMe({ otp_connexion_actif: etat.otp_connexion_actif });
      setNotice(T.otpEnabled);
    } catch (e) {
      if (isApiError(e) && e.status === 409) {
        setBlocked(e.detail === ENVOI_COURRIEL_NON_CONFIGURE ? T.otpEmailNotConfigured : e.detail);
      } else {
        setError(isApiError(e) ? e.detail : fr.errors.generic);
      }
    } finally {
      setPending(false);
    }
  }

  function onToggle() {
    if (pending) return;
    if (active) {
      setNotice("");
      setError(null);
      setConfirming(true);
    } else {
      void enable();
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
          disabled={pending || reason !== null}
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
      {reason && (
        <p id={reasonId} className="mt-2 text-sm text-warning-text">
          {reason}
        </p>
      )}
      {error && (
        <p role="alert" className={`mt-2 ${ALERT_CLASS}`}>
          {error}
        </p>
      )}
      <p role="status" className="mt-2 text-sm text-success-text">
        {notice}
      </p>
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
