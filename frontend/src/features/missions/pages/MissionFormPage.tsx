import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { applyApiErrors } from "@/api/formErrors";
import { isApiError } from "@/api/errors";
import { ForbiddenView } from "@/components/ForbiddenView";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useRole } from "@/auth/useRole";
import { fr } from "@/i18n/fr";
import { useAllDirections, useAllProcesses } from "@/features/referentiel/allPages";
import { useMission, useSaveMission, useSteps } from "../api";
import { CheckGroup } from "../components/CheckGroup";
import { EVENEMENT_DECLENCHEUR_LABELS, TYPE_MISSION_LABELS } from "../labels";
import {
  FORM_FIELDS,
  FROZEN_FIELDS,
  missionSchema,
  toPatch,
  toPayload,
  type MissionFormValues,
} from "../schemas/mission";
import type { EvenementDeclencheur, Mission, TypeMission } from "../types";

const m = fr.missionPilotage;
const TYPES = Object.keys(TYPE_MISSION_LABELS) as TypeMission[];
const TRIGGERS = Object.keys(EVENEMENT_DECLENCHEUR_LABELS) as EvenementDeclencheur[];

/** Champ désactivé lisible (pas d'opacité réduite) : texte plein contraste, fond neutre. */
const FROZEN_CLASS = "disabled:bg-surface-subtle disabled:opacity-100 disabled:cursor-not-allowed";

function defaultsOf(mission?: Mission): MissionFormValues {
  return {
    titre: mission?.titre ?? "",
    type: mission?.type ?? ("" as TypeMission),
    processus: mission?.processus_detail.map((p) => p.id) ?? [],
    entites: mission?.entites_detail.map((e) => e.id) ?? [],
    evenement_declencheur: mission?.evenement_declencheur ?? "",
    evenement_precision: mission?.evenement_precision ?? "",
    periode_debut: mission?.periode_debut ?? "",
    periode_fin: mission?.periode_fin ?? "",
    date_debut_prevue: mission?.date_debut_prevue ?? "",
    date_fin_prevue: mission?.date_fin_prevue ?? "",
    budget_jours: mission?.budget_jours ?? "",
    objectifs: mission?.objectifs ?? "",
    perimetre: mission?.perimetre ?? "",
    exclusions: mission?.exclusions ?? "",
    clients: mission?.clients ?? "",
    livrables_attendus: mission?.livrables_attendus ?? "",
  };
}

export function MissionFormPage() {
  const { id } = useParams();
  const { is } = useRole();
  const mission = useMission(id);
  const steps = useSteps(id);

  if (id === undefined) {
    return is("RAI") ? <MissionForm frozen={false} /> : <ForbiddenView />;
  }
  if (mission.isLoading || steps.isLoading) {
    return <Skeleton role="status" aria-label={fr.common.loading} className="h-64 w-full" />;
  }
  if (mission.isError || !mission.data) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {m.loadError}
      </p>
    );
  }
  if (!mission.data.mes_droits.modifier) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {m.noEdit}
      </p>
    );
  }
  const stepOne = steps.data?.find((s) => s.numero === 1);
  const frozen = stepOne?.statut === "TERMINEE" || stepOne?.statut === "VALIDEE";
  return <MissionForm mission={mission.data} frozen={frozen} />;
}

function MissionForm({ mission, frozen }: { mission?: Mission; frozen: boolean }) {
  const navigate = useNavigate();
  const save = useSaveMission();
  const processes = useAllProcesses({ ordering: "ordre" });
  const entities = useAllDirections({ ordering: "code" });
  const [formError, setFormError] = useState<string | null>(null);
  const [mapMissing, setMapMissing] = useState(false);
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
  } = useForm<MissionFormValues>({
    resolver: zodResolver(missionSchema),
    defaultValues: defaultsOf(mission),
  });

  async function onSubmit(values: MissionFormValues) {
    setFormError(null);
    setMapMissing(false);
    try {
      const saved = await (mission
        ? save.mutateAsync({ id: mission.id, data: toPatch(values, frozen) })
        : save.mutateAsync({ data: toPayload(values) }));
      void navigate(`/missions/${saved.id}`);
    } catch (e) {
      if (isApiError(e) && e.status === 422 && e.errors.cartographie) {
        setMapMissing(true);
        setFormError(e.errors.cartographie.join(" "));
        return;
      }
      setFormError(applyApiErrors(e, setError, FORM_FIELDS));
    }
  }

  const frozenSet = new Set<string>(frozen ? FROZEN_FIELDS : []);
  const lock = (name: keyof MissionFormValues) => frozenSet.has(name);
  const helpFor = (name: keyof MissionFormValues) => (lock(name) ? m.frozenHelp : undefined);
  const back = mission ? `/missions/${mission.id}` : "/missions";

  return (
    <div className="max-w-3xl">
      {/* En modification, l'en-tête de la mission porte déjà le h1 de la page. */}
      {mission ? (
        <h2 className="mb-4 text-2xl font-semibold tracking-[-0.012em]">
          {fr.missions.editMission}
        </h2>
      ) : (
        <h1 className="mb-4 text-2xl font-semibold tracking-[-0.012em]">
          {fr.missions.newMission}
        </h1>
      )}
      {formError && (
        <div role="alert" tabIndex={-1} ref={alertRef} className={`mb-4 ${ALERT_CLASS}`}>
          <p className="font-medium">{m.formErrorTitle}</p>
          <p>{formError}</p>
          {mapMissing && (
            <p className="mt-1">
              {m.mapLinkIntro}{" "}
              <Link to="/referentiel/cartographies" className="font-medium underline">
                {m.mapLink}
              </Link>
              .
            </p>
          )}
        </div>
      )}
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-8">
        <section aria-labelledby="sec-id" className="grid gap-4">
          <h2 id="sec-id" className="text-lg font-semibold">
            {m.sectionIdentification}
          </h2>
          <FormField
            label={fr.missions.fieldTitle}
            error={errors.titre?.message}
            help={helpFor("titre")}
          >
            {(p) => (
              <Input
                {...p}
                maxLength={300}
                disabled={lock("titre")}
                className={FROZEN_CLASS}
                {...register("titre")}
              />
            )}
          </FormField>
          <FormField
            label={fr.missions.fieldType}
            error={errors.type?.message}
            help={helpFor("type")}
          >
            {(p) => (
              <NativeSelect
                {...p}
                disabled={lock("type")}
                className={FROZEN_CLASS}
                {...register("type")}
              >
                <option value="">{m.selectType}</option>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_MISSION_LABELS[t]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        </section>

        <section aria-labelledby="sec-scope" className="grid gap-4">
          <h2 id="sec-scope" className="text-lg font-semibold">
            {m.sectionScope}
          </h2>
          <Controller
            control={control}
            name="processus"
            render={({ field }) => (
              <CheckGroup
                legend={m.fieldProcesses}
                items={(processes.data?.results ?? []).map((p) => ({
                  id: p.id,
                  label: `${p.code} - ${p.libelle}`,
                }))}
                count={processes.data?.count ?? 0}
                isLoading={processes.isLoading}
                isError={processes.isError}
                value={field.value}
                onChange={field.onChange}
                readOnly={lock("processus")}
                help={helpFor("processus")}
                error={errors.processus?.message}
                groupRef={field.ref}
              />
            )}
          />
          <Controller
            control={control}
            name="entites"
            render={({ field }) => (
              <CheckGroup
                legend={m.fieldEntities}
                items={(entities.data?.results ?? []).map((d) => ({
                  id: d.id,
                  label: `${d.code} - ${d.libelle}`,
                }))}
                count={entities.data?.count ?? 0}
                isLoading={entities.isLoading}
                isError={entities.isError}
                value={field.value}
                onChange={field.onChange}
                readOnly={lock("entites")}
                help={helpFor("entites")}
                error={errors.entites?.message}
                groupRef={field.ref}
              />
            )}
          />
          <FormField
            label={m.fieldTrigger}
            error={errors.evenement_declencheur?.message}
            help={helpFor("evenement_declencheur")}
          >
            {(p) => (
              <NativeSelect
                {...p}
                disabled={lock("evenement_declencheur")}
                className={FROZEN_CLASS}
                {...register("evenement_declencheur")}
              >
                <option value="">{m.fieldTriggerNone}</option>
                {TRIGGERS.map((t) => (
                  <option key={t} value={t}>
                    {EVENEMENT_DECLENCHEUR_LABELS[t]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={m.fieldTriggerDetail}
            error={errors.evenement_precision?.message}
            help={helpFor("evenement_precision")}
          >
            {(p) => (
              <Input
                {...p}
                disabled={lock("evenement_precision")}
                className={FROZEN_CLASS}
                {...register("evenement_precision")}
              />
            )}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label={m.fieldPeriodStart}
              error={errors.periode_debut?.message}
              help={helpFor("periode_debut")}
            >
              {(p) => (
                <Input
                  {...p}
                  type="date"
                  disabled={lock("periode_debut")}
                  className={FROZEN_CLASS}
                  {...register("periode_debut")}
                />
              )}
            </FormField>
            <FormField
              label={m.fieldPeriodEnd}
              error={errors.periode_fin?.message}
              help={helpFor("periode_fin")}
            >
              {(p) => (
                <Input
                  {...p}
                  type="date"
                  disabled={lock("periode_fin")}
                  className={FROZEN_CLASS}
                  {...register("periode_fin")}
                />
              )}
            </FormField>
          </div>
        </section>

        <section aria-labelledby="sec-cal" className="grid gap-4">
          <h2 id="sec-cal" className="text-lg font-semibold">
            {m.sectionCalendar}
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label={fr.missions.fieldStart} error={errors.date_debut_prevue?.message}>
              {(p) => <Input {...p} type="date" {...register("date_debut_prevue")} />}
            </FormField>
            <FormField label={fr.missions.fieldEnd} error={errors.date_fin_prevue?.message}>
              {(p) => <Input {...p} type="date" {...register("date_fin_prevue")} />}
            </FormField>
            <FormField label={m.fieldBudget} error={errors.budget_jours?.message}>
              {(p) => (
                <Input {...p} type="number" min={0} step="0.5" {...register("budget_jours")} />
              )}
            </FormField>
          </div>
        </section>

        <section aria-labelledby="sec-obj" className="grid gap-4">
          <h2 id="sec-obj" className="text-lg font-semibold">
            {m.sectionObjectives}
          </h2>
          {(
            [
              ["objectifs", fr.missions.fieldObjectives],
              ["perimetre", fr.missions.fieldScope],
              ["exclusions", m.fieldExclusions],
              ["clients", m.fieldClients],
              ["livrables_attendus", m.fieldDeliverables],
            ] as const
          ).map(([name, label]) => (
            <FormField key={name} label={label} error={errors[name]?.message} help={helpFor(name)}>
              {(p) => (
                <Textarea
                  {...p}
                  rows={3}
                  disabled={lock(name)}
                  className={FROZEN_CLASS}
                  {...register(name)}
                />
              )}
            </FormField>
          ))}
        </section>

        <div className="flex flex-wrap items-center gap-3 print:hidden">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? m.saving : m.saveDraft}
          </Button>
          <Button asChild variant="outline">
            <Link to={back}>{mission ? m.backToMission : m.backToList}</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
