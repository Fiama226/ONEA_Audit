import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { applyApiErrors } from "@/api/formErrors";
import { useDirectionOptions, useUpdateProfile } from "../api";
import { directionLabel } from "../labels";
import { profileSchema, type ProfileFormValues } from "../schemas";
import type { CompteUtilisateur, ProfilInput } from "../types";

const t = fr.utilisateurs.fiche;
const FIELDS = [
  "first_name",
  "last_name",
  "email",
  "matricule",
  "fonction",
  "direction_code",
] as const;
type Field = (typeof FIELDS)[number];

function valuesOf(account: CompteUtilisateur): ProfileFormValues {
  return {
    first_name: account.first_name,
    last_name: account.last_name,
    email: account.email,
    matricule: account.matricule,
    fonction: account.fonction,
    direction_code: account.direction_code,
  };
}

/**
 * Droit requis par champ (le serveur le vérifie de nouveau) : courriel = réinitialiser les mots
 * de passe ; direction = changer les rôles ; autres champs = créer des comptes.
 */
function editableFields(account: CompteUtilisateur): Record<Field, boolean> {
  const { modifier_profil, modifier_courriel, modifier_direction } = account.actions;
  return {
    first_name: modifier_profil,
    last_name: modifier_profil,
    matricule: modifier_profil,
    fonction: modifier_profil,
    email: modifier_courriel,
    direction_code: modifier_direction,
  };
}

/** Profil modifiable champ par champ selon les droits ; n'envoie que les champs modifiés. */
export function ProfileForm({ account }: { account: CompteUtilisateur }) {
  const update = useUpdateProfile();
  const directions = useDirectionOptions();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty, dirtyFields },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: valuesOf(account),
  });

  const { first_name, last_name, email, matricule, fonction, direction_code } = account;
  // Une valeur rafraîchie côté serveur devient la nouvelle référence.
  useEffect(() => {
    reset({ first_name, last_name, email, matricule, fonction, direction_code });
  }, [first_name, last_name, email, matricule, fonction, direction_code, reset]);

  const editable = editableFields(account);
  const anyEditable = FIELDS.some((f) => editable[f]);
  const partial = anyEditable && FIELDS.some((f) => !editable[f]);
  const known = directions.options.some((d) => d.code === account.direction_code);

  async function onSubmit(values: ProfileFormValues) {
    setFormError(null);
    setSaved(false);
    const data: ProfilInput = {};
    for (const field of FIELDS) {
      if (dirtyFields[field] && editable[field]) data[field] = values[field];
    }
    try {
      await update.mutateAsync({ id: account.id, data });
      reset(values);
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  const text = (field: Exclude<Field, "direction_code">, label: string, type = "text") => (
    <FormField label={label} error={errors[field]?.message}>
      {(p) => (
        <Input
          {...p}
          type={type}
          autoComplete="off"
          disabled={!editable[field]}
          {...register(field)}
        />
      )}
    </FormField>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.profileTitle}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
          {formError && (
            <p role="alert" className={ALERT_CLASS}>
              {formError}
            </p>
          )}
          {directions.incomplete && (
            <p className="text-sm text-warning-text">{t.directionsIncomplete}</p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {text("first_name", t.firstName)}
            {text("last_name", t.lastName)}
            {text("email", t.email, "email")}
            {text("matricule", t.matricule)}
            {text("fonction", t.fonction)}
            <FormField label={t.direction} error={errors.direction_code?.message}>
              {(p) => (
                <Controller
                  control={control}
                  name="direction_code"
                  render={({ field }) => (
                    <NativeSelect
                      {...p}
                      disabled={!editable.direction_code}
                      name={field.name}
                      ref={field.ref}
                      value={field.value}
                      onBlur={field.onBlur}
                      onChange={field.onChange}
                    >
                      <option value="">{t.directionNone}</option>
                      {!known && account.direction_code !== "" && (
                        <option value={account.direction_code}>
                          {directionLabel(account.direction_code, account.direction_libelle)}
                        </option>
                      )}
                      {directions.options.map((d) => (
                        <option key={d.id} value={d.code}>
                          {directionLabel(d.code, d.libelle)}
                        </option>
                      ))}
                    </NativeSelect>
                  )}
                />
              )}
            </FormField>
          </div>
          {partial && <p className="text-sm text-text-muted">{t.profilePartial}</p>}
          <p role="status" className="text-sm text-success-text">
            {saved && !isDirty ? t.profileSaved : ""}
          </p>
          {anyEditable && (
            <div className="flex flex-wrap gap-2 print:hidden">
              <Button type="submit" disabled={!isDirty || update.isPending}>
                {update.isPending ? t.saving : t.saveProfile}
              </Button>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
