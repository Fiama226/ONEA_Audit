import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useDeleteProcess, useDirections, useProcess, useSaveProcess } from "../api";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { ALERT_CLASS, FormField, SELECT_CLASS } from "../components/FormField";
import { applyApiErrors } from "../formErrors";
import { FAMILLE_LABELS } from "../labels";
import { canEditStructure } from "../permissions";
import { processSchema, type ProcessFormValues } from "../schemas/process";
import type { Direction, FamilleProcessus, Processus } from "../types";

const s = fr.refStructure;
const FAMILIES = Object.keys(FAMILLE_LABELS) as FamilleProcessus[];

export function ProcessFormPage() {
  const { id } = useParams();
  const process = useProcess(id);
  const directions = useDirections({ type: "DIRECTION", page_size: 100, ordering: "code" });

  if (id !== undefined && process.isLoading) {
    return (
      <Skeleton role="status" aria-label={fr.common.loading} className="h-64 w-full max-w-xl" />
    );
  }
  if (id !== undefined && process.isError) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{s.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void process.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  return <ProcessForm process={process.data} directions={directions.data?.results ?? []} />;
}

function ProcessForm({ process, directions }: { process?: Processus; directions: Direction[] }) {
  const { me } = useAuth();
  const editable = canEditStructure(me?.role ?? null);
  const navigate = useNavigate();
  const save = useSaveProcess();
  const remove = useDeleteProcess();
  const [formError, setFormError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ProcessFormValues>({
    resolver: zodResolver(processSchema),
    defaultValues: {
      code: process?.code ?? "",
      libelle: process?.libelle ?? "",
      famille: process?.famille,
      ordre: process?.ordre ?? 0,
      directions: process?.directions_detail.map((d) => d.id) ?? [],
    },
  });

  async function onSubmit(values: ProcessFormValues) {
    setFormError(null);
    try {
      if (process) {
        const data = {
          libelle: values.libelle,
          famille: values.famille,
          ordre: values.ordre,
          directions: values.directions,
        };
        await save.mutateAsync({ id: process.id, data });
      } else {
        await save.mutateAsync({ data: values });
      }
      void navigate("/referentiel/processus");
    } catch (e) {
      setFormError(
        applyApiErrors(e, setError, ["code", "libelle", "famille", "ordre", "directions"]),
      );
    }
  }

  const title = process ? (editable ? s.editProcessTitle : s.viewProcessTitle) : s.newProcessTitle;

  return (
    <div className="max-w-xl">
      <h2 className="mb-4 text-xl font-semibold">{title}</h2>
      {!editable && <p className="mb-4 text-sm text-text-muted">{s.readOnlyNotice}</p>}
      {formError && (
        <div role="alert" tabIndex={-1} ref={(el) => el?.focus()} className={`mb-4 ${ALERT_CLASS}`}>
          <p className="font-medium">{s.formErrorTitle}</p>
          <p>{formError}</p>
        </div>
      )}
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate>
        <fieldset disabled={!editable} className="grid gap-4">
          <FormField
            label={fr.referentiel.code}
            error={errors.code?.message}
            help={process ? s.codeLocked : s.codeHelp}
          >
            {(p) => (
              <Input
                {...p}
                autoComplete="off"
                maxLength={5}
                disabled={process !== undefined}
                {...register("code")}
              />
            )}
          </FormField>
          <FormField label={fr.referentiel.libelle} error={errors.libelle?.message}>
            {(p) => <Input {...p} maxLength={200} {...register("libelle")} />}
          </FormField>
          <FormField label={fr.referentiel.famille} error={errors.famille?.message}>
            {(p) => (
              <select {...p} className={SELECT_CLASS} {...register("famille")}>
                <option value="">{s.selectFamily}</option>
                {FAMILIES.map((f) => (
                  <option key={f} value={f}>
                    {FAMILLE_LABELS[f]}
                  </option>
                ))}
              </select>
            )}
          </FormField>
          <FormField label={fr.referentiel.ordre} error={errors.ordre?.message}>
            {(p) => (
              <Input
                {...p}
                type="number"
                min={0}
                step={1}
                {...register("ordre", { valueAsNumber: true })}
              />
            )}
          </FormField>
          <fieldset className="grid gap-2">
            <legend className="text-sm font-medium">{s.directionsFieldset}</legend>
            <p className="text-xs text-text-muted">{s.directionsHelp}</p>
            {directions.length === 0 && (
              <p className="text-sm text-text-muted">{s.noDirectionAvailable}</p>
            )}
            <Controller
              control={control}
              name="directions"
              render={({ field }) => (
                <ul className="grid gap-1">
                  {directions.map((d) => (
                    <li key={d.id}>
                      <label className="flex min-h-9 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="size-4 accent-primary"
                          checked={field.value.includes(d.id)}
                          onChange={(e) =>
                            field.onChange(
                              e.target.checked
                                ? [...field.value, d.id]
                                : field.value.filter((v) => v !== d.id),
                            )
                          }
                        />
                        {d.code} - {d.libelle}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            />
          </fieldset>
        </fieldset>

        <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
          {editable && (
            <Button type="submit" disabled={save.isPending}>
              {fr.common.save}
            </Button>
          )}
          <Button asChild variant="outline">
            <Link to="/referentiel/processus">{s.backToList}</Link>
          </Button>
          {editable && process && (
            <Button
              type="button"
              variant="destructive"
              className="ml-auto"
              onClick={() => setConfirming(true)}
            >
              {s.deleteProcess}
            </Button>
          )}
        </div>
      </form>
      {process && (
        <ConfirmDeleteDialog
          open={confirming}
          onOpenChange={setConfirming}
          title={s.deleteProcessTitle}
          description={s.deleteProcessText}
          onConfirm={async () => {
            await remove.mutateAsync(process.id);
            void navigate("/referentiel/processus");
          }}
        />
      )}
    </div>
  );
}
