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
import { useAccountAction, useDirectionOptions, useUpdateProfile } from "../api";
import { directionLabel } from "../labels";
import { profileSchema, type ProfileFormValues } from "../schemas";
import type { CompteUtilisateur, ProfilInput } from "../types";

const t = fr.utilisateurs.fiche;
const FIELDS = ["matricule", "fonction", "direction_code"] as const;

function valuesOf(account: CompteUtilisateur): ProfileFormValues {
  return {
    matricule: account.matricule,
    fonction: account.fonction,
    direction_code: account.direction_code,
  };
}

/** Profil modifiable (matricule, fonction, direction) ; n'envoie que les champs modifiés. */
export function ProfileForm({ account }: { account: CompteUtilisateur }) {
  const update = useUpdateProfile();
  const action = useAccountAction();
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

  // Une valeur rafraîchie côté serveur (enregistrement, rétablissement) devient la nouvelle référence.
  useEffect(() => {
    reset({
      matricule: account.matricule,
      fonction: account.fonction,
      direction_code: account.direction_code,
    });
  }, [account.matricule, account.fonction, account.direction_code, reset]);

  const canEdit = account.actions.modifier_profil;
  const known = directions.options.some((d) => d.code === account.direction_code);

  async function onSubmit(values: ProfileFormValues) {
    setFormError(null);
    setSaved(false);
    const data: ProfilInput = {};
    for (const field of FIELDS) {
      if (dirtyFields[field]) data[field] = values[field];
    }
    try {
      await update.mutateAsync({ id: account.id, data });
      reset(values);
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  async function resync() {
    setFormError(null);
    setSaved(false);
    try {
      await action.mutateAsync({ id: account.id, action: "resync-profile" });
    } catch (e) {
      setFormError(applyApiErrors(e, setError, []));
    }
  }

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
            <FormField label={t.matricule} error={errors.matricule?.message}>
              {(p) => (
                <Input {...p} autoComplete="off" disabled={!canEdit} {...register("matricule")} />
              )}
            </FormField>
            <FormField label={t.fonction} error={errors.fonction?.message}>
              {(p) => (
                <Input {...p} autoComplete="off" disabled={!canEdit} {...register("fonction")} />
              )}
            </FormField>
            <FormField label={t.direction} error={errors.direction_code?.message}>
              {(p) => (
                <Controller
                  control={control}
                  name="direction_code"
                  render={({ field }) => (
                    <NativeSelect
                      {...p}
                      disabled={!canEdit}
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
          <p className="text-sm text-text-muted">
            {account.profil_gere_localement ? t.profileLocal : t.profileFromDirectory}
          </p>
          <p role="status" className="text-sm text-success-text">
            {saved && !isDirty ? t.profileSaved : ""}
          </p>
          {canEdit && (
            <div className="flex flex-wrap gap-2 print:hidden">
              <Button type="submit" disabled={!isDirty || update.isPending}>
                {update.isPending ? t.saving : t.saveProfile}
              </Button>
              {account.profil_gere_localement && account.actions.resynchroniser_profil && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={action.isPending}
                  onClick={() => void resync()}
                >
                  {t.resyncProfile}
                </Button>
              )}
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
