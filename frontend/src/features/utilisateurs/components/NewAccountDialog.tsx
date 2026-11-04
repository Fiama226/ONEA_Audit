import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { applyApiErrors } from "@/api/formErrors";
import { useAccountRights } from "@/auth/useAccountRights";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
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
import { useCreateAccount, useDirectionOptions } from "../api";
import { assignableRoles, directionLabel, ROLE_LABELS } from "../labels";
import { newAccountSchema, type NewAccountFormValues } from "../schemas";
import type { CreationCompteInput, MotDePasseTemporaire, Role } from "../types";
import { TemporaryPassword } from "./TemporaryPassword";

const c = fr.utilisateurs.creation;
const t = fr.utilisateurs.fiche;

const FIELDS = [
  "username",
  "first_name",
  "last_name",
  "email",
  "role",
  "matricule",
  "direction_code",
  "fonction",
  "envoyer_courriel",
] as const;

const EMPTY: NewAccountFormValues = {
  username: "",
  first_name: "",
  last_name: "",
  email: "",
  role: "",
  matricule: "",
  direction_code: "",
  fonction: "",
  // Le courriel de bienvenue part par défaut (ce n'est pas un consentement).
  envoyer_courriel: true,
};

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

/** « Nouvel agent » : formulaire, puis résultat (courriel parti ou mot de passe affiché une fois). */
export function NewAccountDialog({ open, onOpenChange }: Props) {
  // Verrou : création en cours, ou mot de passe affiché. Seul le bouton explicite ferme alors la
  // fenêtre (ni Échap, ni clic à l'extérieur) : le mot de passe ne se perd pas par mégarde.
  const [locked, setLocked] = useState(false);
  const guard = (event: Event) => {
    if (locked) event.preventDefault();
  };
  return (
    <Dialog open={open} onOpenChange={(next) => (next || !locked) && onOpenChange(next)}>
      <DialogContent
        showCloseButton={false}
        className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"
        onEscapeKeyDown={guard}
        onPointerDownOutside={guard}
        onInteractOutside={guard}
      >
        <NewAccount onLockChange={setLocked} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function NewAccount({
  onClose,
  onLockChange,
}: {
  onClose: () => void;
  onLockChange: (locked: boolean) => void;
}) {
  const mutation = useCreateAccount();
  /** Résultat tenu par ce seul composant (démonté à la fermeture), jamais par un cache. */
  const [result, setResult] = useState<MotDePasseTemporaire | null>(null);
  const locked = mutation.isPending || Boolean(result?.mot_de_passe_temporaire);
  useEffect(() => onLockChange(locked), [locked, onLockChange]);

  async function create(data: CreationCompteInput): Promise<void> {
    const response = await mutation.mutateAsync(data);
    // Le cache des mutations ne garde pas la réponse (et donc pas le mot de passe).
    mutation.reset();
    setResult(response);
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{c.title}</DialogTitle>
        <DialogDescription>{c.description}</DialogDescription>
      </DialogHeader>
      {result ? (
        <CreatedAccount result={result} onClose={onClose} />
      ) : (
        <NewAccountForm onCreate={create} onCancel={onClose} pending={mutation.isPending} />
      )}
    </>
  );
}

function NewAccountForm({
  onCreate,
  onCancel,
  pending,
}: {
  onCreate: (data: CreationCompteInput) => Promise<void>;
  onCancel: () => void;
  pending: boolean;
}) {
  const { isAdmin } = useAccountRights();
  const directions = useDirectionOptions();
  const sendEmailHelp = useId();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<NewAccountFormValues>({
    resolver: zodResolver(newAccountSchema),
    defaultValues: EMPTY,
  });

  async function onSubmit(values: NewAccountFormValues) {
    setFormError(null);
    try {
      await onCreate({ ...values, role: values.role as Role });
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={c.username} help={c.usernameHelp} error={errors.username?.message}>
          {(p) => <Input {...p} autoComplete="off" {...register("username")} />}
        </FormField>
        <FormField
          label={c.role}
          help={isAdmin ? undefined : c.roleAdminOnly}
          error={errors.role?.message}
        >
          {(p) => (
            <NativeSelect {...p} {...register("role")}>
              <option value="">{c.rolePlaceholder}</option>
              {assignableRoles(isAdmin).map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <FormField label={t.firstName} error={errors.first_name?.message}>
          {(p) => <Input {...p} autoComplete="off" {...register("first_name")} />}
        </FormField>
        <FormField label={t.lastName} error={errors.last_name?.message}>
          {(p) => <Input {...p} autoComplete="off" {...register("last_name")} />}
        </FormField>
        <FormField label={t.email} error={errors.email?.message}>
          {(p) => <Input {...p} type="email" autoComplete="off" {...register("email")} />}
        </FormField>
        <FormField label={t.matricule} error={errors.matricule?.message}>
          {(p) => <Input {...p} autoComplete="off" {...register("matricule")} />}
        </FormField>
        <FormField label={t.direction} error={errors.direction_code?.message}>
          {(p) => (
            <NativeSelect {...p} {...register("direction_code")}>
              <option value="">{t.directionNone}</option>
              {directions.options.map((d) => (
                <option key={d.id} value={d.code}>
                  {directionLabel(d.code, d.libelle)}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <FormField label={t.fonction} error={errors.fonction?.message}>
          {(p) => <Input {...p} autoComplete="off" {...register("fonction")} />}
        </FormField>
      </div>
      <div className="grid gap-1">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            aria-describedby={sendEmailHelp}
            {...register("envoyer_courriel")}
          />
          {c.sendEmail}
        </label>
        <p id={sendEmailHelp} className="text-xs text-text-muted">
          {c.sendEmailHelp}
        </p>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" disabled={pending} onClick={onCancel}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? c.submitting : c.submit}
        </Button>
      </DialogFooter>
    </form>
  );
}

function CreatedAccount({
  result,
  onClose,
}: {
  result: MotDePasseTemporaire;
  onClose: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { compte, courriel_envoye, mot_de_passe_temporaire } = result;
  // Le formulaire a disparu : le focus va au titre du résultat.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="grid gap-4">
      <h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold outline-none">
        {c.createdTitle}
      </h3>
      <p className="text-sm">{`${compte.nom_complet} (${compte.username})`}</p>
      {courriel_envoye ? (
        <p className="text-sm">{`${c.emailedTo}${compte.email}.`}</p>
      ) : (
        <p className="text-sm">{c.notEmailed}</p>
      )}
      {mot_de_passe_temporaire && <TemporaryPassword value={mot_de_passe_temporaire} />}
      <DialogFooter>
        <Button asChild variant="outline">
          <Link to={`/administration/utilisateurs/${compte.id}`}>{c.openRecord}</Link>
        </Button>
        <Button type="button" onClick={onClose}>
          {mot_de_passe_temporaire ? fr.utilisateurs.motDePasse.acknowledge : fr.common.close}
        </Button>
      </DialogFooter>
    </div>
  );
}
