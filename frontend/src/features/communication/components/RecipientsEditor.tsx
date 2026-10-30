import { useState } from "react";
import { applyApiErrors } from "@/api/formErrors";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { UserPicker } from "@/features/missions/components/UserPicker";
import { fr } from "@/i18n/fr";
import { useForm } from "react-hook-form";
import { useRecipients, useRemoveRecipient, useSaveRecipient } from "../api";
import { CATEGORIE_DESTINATAIRE_LABELS } from "../labels";
import type { CategorieDestinataire, Destinataire } from "../types";

const t = fr.rapportFinal;
const CATEGORIES = Object.keys(CATEGORIE_DESTINATAIRE_LABELS) as CategorieDestinataire[];

export function recipientName(d: Destinataire): string {
  return d.utilisateur_detail?.nom_complet ?? d.nom_externe;
}

type Props = { rapportId: string; missionId: string; readOnly?: boolean };

type ExternalValues = { nom_externe: string; qualite: string; categorie: CategorieDestinataire };

/** Liste de diffusion : internes via le sélecteur d'utilisateurs, externes (nom, qualité), catégories. */
export function RecipientsEditor({ rapportId, missionId, readOnly = false }: Props) {
  const recipients = useRecipients(rapportId);
  const save = useSaveRecipient();
  const remove = useRemoveRecipient();
  const [category, setCategory] = useState<CategorieDestinataire>("AUTRE");
  const [error, setError] = useState<string | null>(null);

  if (recipients.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.recipientsError}
      </p>
    );
  }
  if (!recipients.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const list = recipients.data.results;
  const internal = list.filter((d) => d.utilisateur !== null);

  function fail(e: unknown) {
    setError(isApiError(e) ? e.detail : t.recipientSaveError);
  }

  async function changeInternal(ids: string[]) {
    setError(null);
    const current = new Map(internal.map((d) => [String(d.utilisateur), d]));
    try {
      for (const id of ids.filter((i) => !current.has(i))) {
        await save.mutateAsync({
          missionId,
          data: {
            rapport: rapportId,
            utilisateur: Number(id),
            nom_externe: "",
            qualite: "",
            categorie: category,
          },
        });
      }
      for (const [id, d] of current) {
        if (!ids.includes(id)) await remove.mutateAsync({ id: d.id, missionId });
      }
    } catch (e) {
      fail(e);
    }
  }

  async function changeCategory(d: Destinataire, categorie: CategorieDestinataire) {
    setError(null);
    try {
      await save.mutateAsync({ id: d.id, missionId, data: { categorie } });
    } catch (e) {
      fail(e);
    }
  }

  async function removeOne(d: Destinataire) {
    setError(null);
    try {
      await remove.mutateAsync({ id: d.id, missionId });
    } catch (e) {
      fail(e);
    }
  }

  return (
    <section aria-labelledby="recipients-title" className="grid gap-3">
      <h3 id="recipients-title" className="text-base font-semibold">
        {t.recipientsTitle}
      </h3>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      {list.length === 0 ? (
        <p className="text-sm text-text-muted">{t.recipientsEmpty}</p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">{t.recipientsCaption}</caption>
          <thead>
            <tr className="border-b border-border text-left">
              <th scope="col" className="py-1 pr-3">
                {t.recipientName}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.recipientQuality}
              </th>
              <th scope="col" className="py-1 pr-3">
                {t.recipientCategory}
              </th>
              {!readOnly && (
                <th scope="col" className="py-1">
                  <span className="sr-only">{fr.common.actions}</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {list.map((d) => (
              <tr key={d.id} className="border-b border-border">
                <td className="py-1 pr-3">{recipientName(d)}</td>
                <td className="py-1 pr-3">{d.qualite || d.utilisateur_detail?.fonction || "—"}</td>
                <td className="py-1 pr-3">
                  {readOnly ? (
                    CATEGORIE_DESTINATAIRE_LABELS[d.categorie]
                  ) : (
                    <NativeSelect
                      aria-label={`${t.recipientCategory} — ${recipientName(d)}`}
                      value={d.categorie}
                      onChange={(e) =>
                        void changeCategory(d, e.target.value as CategorieDestinataire)
                      }
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {CATEGORIE_DESTINATAIRE_LABELS[c]}
                        </option>
                      ))}
                    </NativeSelect>
                  )}
                </td>
                {!readOnly && (
                  <td className="py-1 text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void removeOne(d)}
                    >
                      {t.recipientRemove.replace("{nom}", recipientName(d))}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!readOnly && (
        <>
          <FormField label={t.recipientInternalCategory}>
            {(p) => (
              <NativeSelect
                {...p}
                value={category}
                onChange={(e) => setCategory(e.target.value as CategorieDestinataire)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORIE_DESTINATAIRE_LABELS[c]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <UserPicker
            label={t.recipientInternal}
            value={internal.map((d) => String(d.utilisateur))}
            onChange={(ids) => void changeInternal(ids)}
            known={internal.flatMap((d) => (d.utilisateur_detail ? [d.utilisateur_detail] : []))}
          />
          <ExternalForm rapportId={rapportId} missionId={missionId} />
        </>
      )}
    </section>
  );
}

const EXTERNAL_FIELDS = ["nom_externe", "qualite", "categorie"] as const;

function ExternalForm({ rapportId, missionId }: { rapportId: string; missionId: string }) {
  const save = useSaveRecipient();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<ExternalValues>({
    defaultValues: { nom_externe: "", qualite: "", categorie: "AUTRE" },
  });

  async function onSubmit(values: ExternalValues) {
    setFormError(null);
    try {
      await save.mutateAsync({ missionId, data: { rapport: rapportId, ...values } });
      reset();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, EXTERNAL_FIELDS));
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      noValidate
      aria-label={t.recipientExternal}
      className="grid gap-3 rounded-md border border-border p-3"
    >
      <p className="text-sm font-medium">{t.recipientExternal}</p>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.recipientExternalName} error={errors.nom_externe?.message}>
        {(p) => <Input {...p} {...register("nom_externe")} />}
      </FormField>
      <FormField label={t.recipientExternalQuality} error={errors.qualite?.message}>
        {(p) => <Input {...p} {...register("qualite")} />}
      </FormField>
      <FormField label={t.recipientCategory} error={errors.categorie?.message}>
        {(p) => (
          <NativeSelect {...p} {...register("categorie")}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORIE_DESTINATAIRE_LABELS[c]}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <div>
        <Button type="submit" variant="outline" disabled={save.isPending}>
          {t.recipientAdd}
        </Button>
      </div>
    </form>
  );
}
