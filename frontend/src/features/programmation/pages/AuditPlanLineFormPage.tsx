import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useRef, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAllDirections, useAllProcesses } from "@/features/referentiel/allPages";
import { useAuditableTree } from "@/features/referentiel/api";
import { fr } from "@/i18n/fr";
import {
  useAuditPlan,
  useAuditPlanLine,
  useDeleteAuditPlanLine,
  useSaveAuditPlanLine,
} from "../api";
import { DeleteLineDialog } from "../components/DeleteLineDialog";
import { EntitiesPicker } from "../components/EntitiesPicker";
import { INTERVENTION_TYPE_LABELS } from "../labels";
import { canEditAuditPlan } from "../permissions";
import { lineSchema, toDecimal, type LineFormValues } from "../schemas/line";
import {
  ALERT_CLASS,
  applyApiErrors,
  FormField,
  ListIncompleteAlert,
  NativeSelect,
} from "../shared";
import type { AuditPlanLine, InterventionType } from "../types";

const s = fr.programmationLignes;
const p = fr.programmation;
const TYPES = Object.keys(INTERVENTION_TYPE_LABELS) as InterventionType[];
const FIELDS = [
  "titre",
  "type",
  "processus",
  "objet_auditable",
  "entites",
  "debut_prevu",
  "fin_prevue",
  "charge_prevue_jours",
  "justification",
] as const;

/** `creating` : création sous `:id/nouvelle-ligne` ; sinon modification ou lecture de `lignes/:lineId`. */
export function AuditPlanLineFormPage({ creating = false }: { creating?: boolean }) {
  const { id, lineId } = useParams();
  const { me } = useAuth();
  const plan = useAuditPlan(creating ? id : undefined);
  const line = useAuditPlanLine(creating ? undefined : lineId);
  const query = creating ? plan : line;

  if (query.isLoading || (query.isPending && query.fetchStatus !== "idle")) {
    return (
      <Skeleton role="status" aria-label={fr.common.loading} className="h-64 w-full max-w-xl" />
    );
  }
  if (query.isError || !query.data) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{s.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void query.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  const context = creating
    ? { planId: plan.data!.id, year: plan.data!.annee, validated: plan.data!.statut === "VALIDE" }
    : {
        planId: line.data!.programme,
        year: line.data!.programme_annee,
        validated: line.data!.programme_statut === "VALIDE",
      };
  return (
    <LineForm
      {...context}
      line={creating ? undefined : line.data}
      canWrite={canEditAuditPlan(me?.role ?? null)}
    />
  );
}

type Props = {
  planId: string;
  year: number;
  validated: boolean;
  canWrite: boolean;
  line?: AuditPlanLine;
};

function LineForm({ planId, year, validated, canWrite, line }: Props) {
  const readOnly = validated || !canWrite;
  const navigate = useNavigate();
  const save = useSaveAuditPlanLine();
  const remove = useDeleteAuditPlanLine();
  const processes = useAllProcesses({ ordering: "code" });
  const directions = useAllDirections({ ordering: "code" });
  const [formError, setFormError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const alertRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (formError) alertRef.current?.focus();
  }, [formError]);

  const schema = useMemo(() => lineSchema(year), [year]);
  const {
    register,
    control,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<LineFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      titre: line?.titre ?? "",
      type: line?.type ?? "ASSURANCE",
      processus: line?.processus ?? "",
      objet_auditable: line?.objet_auditable ?? "",
      entites: line?.entites_detail.map((e) => e.id) ?? [],
      debut_prevu: line?.debut_prevu ?? "",
      fin_prevue: line?.fin_prevue ?? "",
      charge_prevue_jours: line?.charge_prevue_jours ?? "",
      justification: line?.justification ?? "",
    },
  });
  const processId = useWatch({ control, name: "processus" });
  const tree = useAuditableTree(processId || undefined);

  async function onSubmit(v: LineFormValues) {
    setFormError(null);
    const data = {
      titre: v.titre,
      type: v.type,
      processus: v.processus,
      objet_auditable: v.objet_auditable || null,
      entites: v.entites,
      debut_prevu: v.debut_prevu,
      fin_prevue: v.fin_prevue,
      charge_prevue_jours: toDecimal(v.charge_prevue_jours),
      justification: v.justification,
    };
    try {
      if (line) await save.mutateAsync({ id: line.id, data });
      else await save.mutateAsync({ data: { programme: planId, ...data } });
      void navigate(`/programme-annuel/${planId}`, { state: { flash: s.saved } });
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-2xl font-semibold">{line ? s.editTitle : s.newTitle}</h1>
      {readOnly && (
        <p role="status" className="mb-4 text-sm font-medium text-text-muted">
          {s.readOnly}
        </p>
      )}
      {line && (
        <p className="mb-4 text-sm">
          <span className="text-text-muted">{s.numberLabel} : </span>
          <span className="tabular-nums font-medium">{line.numero}</span>
        </p>
      )}
      {formError && (
        <div role="alert" tabIndex={-1} ref={alertRef} className={`mb-4 ${ALERT_CLASS}`}>
          <p className="font-medium">{s.formErrorTitle}</p>
          <p>{formError}</p>
        </div>
      )}
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate>
        <fieldset
          disabled={readOnly}
          className="grid gap-4 border-0 p-0 [&_:disabled]:opacity-100!"
        >
          <FormField label={s.lineTitle} error={errors.titre?.message}>
            {(f) => <Input {...f} maxLength={300} {...register("titre")} />}
          </FormField>

          <fieldset className="grid gap-1.5">
            <legend className="text-sm font-medium">{s.typeLegend}</legend>
            <div className="flex gap-4">
              {TYPES.map((t) => (
                <label key={t} className="flex min-h-9 items-center gap-2 text-sm">
                  <input
                    type="radio"
                    className="size-4 accent-primary"
                    value={t}
                    {...register("type")}
                  />
                  {INTERVENTION_TYPE_LABELS[t]}
                </label>
              ))}
            </div>
            {errors.type && <p className="text-sm text-destructive">{errors.type.message}</p>}
          </fieldset>

          <FormField label={p.process} error={errors.processus?.message}>
            {(f) => (
              <>
                <NativeSelect
                  {...f}
                  {...register("processus", {
                    onChange: () => setValue("objet_auditable", ""),
                  })}
                >
                  <option value="">{s.selectProcess}</option>
                  {(processes.data?.results ?? []).map((pr) => (
                    <option key={pr.id} value={pr.id}>
                      {pr.code} - {pr.libelle}
                    </option>
                  ))}
                </NativeSelect>
                {processes.data && (
                  <ListIncompleteAlert
                    count={processes.data.count}
                    loaded={processes.data.results.length}
                  />
                )}
              </>
            )}
          </FormField>

          <FormField
            label={p.auditableObject}
            error={errors.objet_auditable?.message}
            help={s.auditableObjectHelp}
          >
            {(f) => (
              <NativeSelect {...f} {...register("objet_auditable")}>
                <option value="">{s.noAuditableObject}</option>
                {(tree.data ?? []).map((d) => (
                  <optgroup key={d.id} label={d.libelle}>
                    <option value={d.id}>
                      {d.libelle} {s.domainSuffix}
                    </option>
                    {d.operations.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.libelle}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </NativeSelect>
            )}
          </FormField>

          <Controller
            control={control}
            name="entites"
            render={({ field }) => (
              <EntitiesPicker
                directions={directions.data?.results ?? []}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
          {directions.data && (
            <ListIncompleteAlert
              count={directions.data.count}
              loaded={directions.data.results.length}
            />
          )}
          {errors.entites && <p className="text-sm text-destructive">{errors.entites.message}</p>}

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label={p.plannedStart}
              error={errors.debut_prevu?.message}
              help={s.startHelp}
            >
              {(f) => <Input {...f} type="date" {...register("debut_prevu")} />}
            </FormField>
            <FormField label={p.plannedEnd} error={errors.fin_prevue?.message}>
              {(f) => <Input {...f} type="date" {...register("fin_prevue")} />}
            </FormField>
          </div>

          <FormField
            label={p.plannedDays}
            error={errors.charge_prevue_jours?.message}
            help={s.daysHelp}
          >
            {(f) => (
              <Input
                {...f}
                inputMode="decimal"
                className="max-w-40"
                {...register("charge_prevue_jours")}
              />
            )}
          </FormField>

          <FormField
            label={p.justification}
            error={errors.justification?.message}
            help={s.justificationHelp}
          >
            {(f) => (
              <textarea {...f} rows={4} className={TEXTAREA} {...register("justification")} />
            )}
          </FormField>
        </fieldset>

        <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
          {!readOnly && (
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? s.saving : s.save}
            </Button>
          )}
          <Button asChild variant="outline">
            <Link to={`/programme-annuel/${planId}`}>{s.back}</Link>
          </Button>
          {line && !readOnly && (
            <Button
              type="button"
              variant="destructive"
              className="ml-auto"
              onClick={() => setConfirming(true)}
            >
              {s.deleteLine}
            </Button>
          )}
        </div>
      </form>
      {line && (
        <DeleteLineDialog
          open={confirming}
          onOpenChange={setConfirming}
          onConfirm={async () => {
            await remove.mutateAsync(line.id);
            void navigate(`/programme-annuel/${planId}`);
          }}
        />
      )}
    </div>
  );
}

const TEXTAREA =
  "w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:border-destructive";
