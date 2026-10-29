import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useAllDirections } from "../allPages";
import { useDeleteProcess, useProcess, useSaveProcess } from "../api";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { applyApiErrors } from "@/api/formErrors";
import { FAMILLE_LABELS } from "../labels";
import { canEditStructure } from "../permissions";
import { processSchema, type ProcessFormValues } from "../schemas/process";
import type { FamilleProcessus, Processus } from "../types";

const s = fr.refStructure;
const FAMILIES = Object.keys(FAMILLE_LABELS) as FamilleProcessus[];

type DirectionsQuery = ReturnType<typeof useAllDirections>;

export function ProcessFormPage() {
  const { id } = useParams();
  const { me } = useAuth();
  const editable = canEditStructure(me?.role ?? null);
  const process = useProcess(id);

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
  return editable ? (
    <ProcessForm process={process.data} />
  ) : (
    <ProcessReadView process={process.data} />
  );
}

/** Vue en lecture seule (rôles sans droit d'écriture) : texte plein contraste, sans champs grisés. */
function ProcessReadView({ process }: { process?: Processus }) {
  const rows: [string, string][] = process
    ? [
        [fr.referentiel.code, process.code],
        [fr.referentiel.libelle, process.libelle],
        [fr.referentiel.famille, FAMILLE_LABELS[process.famille]],
        [fr.referentiel.ordre, String(process.ordre ?? 0)],
        [
          fr.referentiel.directionsRattachees,
          process.directions_detail.map((d) => `${d.code} - ${d.libelle}`).join(", ") ||
            s.noneValue,
        ],
      ]
    : [];
  return (
    <div className="max-w-xl">
      <h2 className="mb-4 text-xl font-semibold">{s.viewProcessTitle}</h2>
      <p className="mb-4 text-sm text-text-muted">{s.readOnlyNotice}</p>
      <dl className="grid gap-3 rounded-lg border border-border bg-surface p-4 text-sm">
        {rows.map(([term, value]) => (
          <div key={term} className="grid gap-0.5">
            <dt className="text-xs font-semibold text-text-muted">{term}</dt>
            <dd className="text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-6 print:hidden">
        <Button asChild variant="outline">
          <Link to="/referentiel/processus">{s.backToList}</Link>
        </Button>
      </div>
    </div>
  );
}

function DirectionsChecklist({
  directions,
  value,
  onChange,
}: {
  directions: DirectionsQuery;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-medium">{s.directionsFieldset}</legend>
      <p className="text-xs text-text-muted">{s.directionsHelp}</p>
      {directions.isLoading && (
        <Skeleton role="status" aria-label={s.loadingDirections} className="h-16 w-full" />
      )}
      {directions.isError && (
        <div role="alert" className={ALERT_CLASS}>
          <p>{s.loadError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void directions.refetch()}
          >
            {fr.common.retry}
          </Button>
        </div>
      )}
      {directions.data && (
        <ListIncompleteAlert
          count={directions.data.count}
          loaded={directions.data.results.length}
        />
      )}
      {directions.data && directions.data.results.length === 0 && (
        <p className="text-sm text-text-muted">{s.noDirectionAvailable}</p>
      )}
      <ul className="grid gap-1">
        {(directions.data?.results ?? []).map((d) => (
          <li key={d.id}>
            <label className="flex min-h-9 items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={value.includes(d.id)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...value, d.id] : value.filter((v) => v !== d.id))
                }
              />
              {d.code} - {d.libelle}
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

function ProcessForm({ process }: { process?: Processus }) {
  const directions = useAllDirections({ type: "DIRECTION", ordering: "code" });
  const navigate = useNavigate();
  const save = useSaveProcess();
  const remove = useDeleteProcess();
  const [formError, setFormError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const alertRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (formError) alertRef.current?.focus();
  }, [formError]);
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

  return (
    <div className="max-w-xl">
      <h2 className="mb-4 text-xl font-semibold">
        {process ? s.editProcessTitle : s.newProcessTitle}
      </h2>
      {formError && (
        <div role="alert" tabIndex={-1} ref={alertRef} className={`mb-4 ${ALERT_CLASS}`}>
          <p className="font-medium">{s.formErrorTitle}</p>
          <p>{formError}</p>
        </div>
      )}
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate>
        <div className="grid gap-4">
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
              <NativeSelect {...p} {...register("famille")}>
                <option value="">{s.selectFamily}</option>
                {FAMILIES.map((f) => (
                  <option key={f} value={f}>
                    {FAMILLE_LABELS[f]}
                  </option>
                ))}
              </NativeSelect>
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
          <Controller
            control={control}
            name="directions"
            render={({ field }) => (
              <DirectionsChecklist
                directions={directions}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? s.saving : fr.common.save}
          </Button>
          <Button asChild variant="outline">
            <Link to="/referentiel/processus">{s.backToList}</Link>
          </Button>
          {process && (
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
