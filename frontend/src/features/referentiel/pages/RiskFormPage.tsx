import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import {
  useAuditableTree,
  useDeleteRisk,
  useProcesses,
  useRisk,
  useRiskMap,
  useSaveRisk,
} from "../api";
import { FrozenBanner } from "../components/FrozenBanner";
import { NativeSelect } from "../components/NativeSelect";
import { RiskLevelBadge } from "../components/RiskLevelBadge";
import { NIVEAU_LABELS, PRIORITE_LABELS, REPONSE_LABELS } from "../labels";
import { canEditCartographie } from "../permissions";
import { applyServerErrors } from "../riskServerErrors";
import {
  niveauFromScore,
  prioriteFromNiveau,
  riskSchema,
  type RiskFormValues,
} from "../schemas/risk";
import type { PrioriteRisque, ReponseRisque, Risque, RisqueInput } from "../types";

const c = fr.refCartographie;
const SCALE = ["1", "2", "3", "4", "5"] as const;
const FIELDS = [
  "processus",
  "objet_auditable",
  "libelle",
  "description",
  "probabilite",
  "impact",
  "vulnerabilite",
  "reponse",
  "priorite",
  "objectif_controle",
  "dispositif_controle",
] as const;

const EMPTY: RiskFormValues = {
  processus: "",
  objet_auditable: "",
  libelle: "",
  description: "",
  probabilite: "1",
  impact: "1",
  vulnerabilite: "",
  reponse: "",
  priorite: "",
  objectif_controle: "",
  dispositif_controle: "",
};

function valuesFromRisk(risk: Risque): RiskFormValues {
  const derived = prioriteFromNiveau(risk.niveau);
  return {
    processus: risk.processus,
    objet_auditable: risk.objet_auditable ?? "",
    libelle: risk.libelle,
    description: risk.description ?? "",
    probabilite: String(risk.probabilite),
    impact: String(risk.impact),
    vulnerabilite: risk.vulnerabilite ?? "",
    reponse: risk.reponse ?? "",
    // Priorité différente de celle dérivée du niveau = choix de l'utilisateur à conserver.
    priorite: risk.priorite && risk.priorite !== derived ? String(risk.priorite) : "",
    objectif_controle: risk.objectif_controle ?? "",
    dispositif_controle: risk.dispositif_controle ?? "",
  };
}

export function RiskFormPage() {
  const { id } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const isEdit = id !== undefined;

  const risk = useRisk(id);
  const versionId = isEdit ? risk.data?.version : (search.get("cartographie") ?? undefined);
  const map = useRiskMap(versionId);
  const processes = useProcesses({ page_size: 200 });
  const save = useSaveRisk();
  const del = useDeleteRisk();
  const [general, setGeneral] = useState("");
  const [saved, setSaved] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const form = useForm<RiskFormValues>({
    resolver: zodResolver(riskSchema),
    defaultValues: EMPTY,
  });
  const processusId = useWatch({ control: form.control, name: "processus" });
  const tree = useAuditableTree(processusId || undefined);

  useEffect(() => {
    if (risk.data) form.reset(valuesFromRisk(risk.data));
  }, [risk.data, form]);

  const [p, i] = useWatch({ control: form.control, name: ["probabilite", "impact"] });
  const score = Number(p) * Number(i);
  const niveau = niveauFromScore(score);
  const derivedPriorite = prioriteFromNiveau(niveau);

  const frozen = (isEdit ? risk.data?.version_statut : map.data?.statut) === "VALIDEE";
  const canEdit = canEditCartographie(role) && !frozen;
  const readOnly = !canEdit;

  if ((isEdit && risk.isLoading) || (versionId && map.isLoading)) {
    return (
      <div aria-busy="true" aria-label={fr.common.loading} className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isEdit && (risk.isError || !risk.data)) {
    const notFound = isApiError(risk.error) && risk.error.status === 404;
    return (
      <p role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        {notFound ? c.riskNotFound : c.riskLoadError}
      </p>
    );
  }
  if (!isEdit && (!versionId || map.isError)) {
    return (
      <p role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        {versionId ? c.notFound : c.riskMapMissing}
      </p>
    );
  }

  const backTo = `/referentiel/cartographies/${versionId}`;

  async function onSubmit(values: RiskFormValues) {
    if (!versionId) return;
    setGeneral("");
    setSaved(false);
    const priorite = (
      values.priorite ? Number(values.priorite) : derivedPriorite
    ) as PrioriteRisque;
    const data: Partial<RisqueInput> = {
      objet_auditable: values.objet_auditable || null,
      libelle: values.libelle,
      description: values.description,
      probabilite: Number(values.probabilite),
      impact: Number(values.impact),
      vulnerabilite: values.vulnerabilite,
      reponse: (values.reponse || "") as ReponseRisque | "",
      priorite,
      objectif_controle: values.objectif_controle,
      dispositif_controle: values.dispositif_controle,
    };
    try {
      if (id) {
        await save.mutateAsync({ id, data });
        setSaved(true);
      } else {
        const created = await save.mutateAsync({
          data: { ...data, version: versionId, processus: values.processus } as RisqueInput,
        });
        void navigate(`/referentiel/risques/${created.id}`, { replace: true });
      }
    } catch (e) {
      setGeneral(applyServerErrors(e, form.setError, FIELDS));
    }
  }

  async function onDelete() {
    if (!id) return;
    setDeleteError("");
    try {
      await del.mutateAsync(id);
      void navigate(backTo);
    } catch (e) {
      setDeleteError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <div className="grid max-w-3xl gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{isEdit ? c.riskTitle : c.riskNewTitle}</h2>
        <Link
          to={backTo}
          className="text-sm text-primary underline-offset-4 hover:underline print:hidden"
        >
          {c.backToMap}
        </Link>
      </div>

      {frozen && map.data && <FrozenBanner version={map.data} />}
      {frozen && !map.data && risk.data && <p role="status">{c.readOnlyNote}</p>}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-6" noValidate>
          <fieldset disabled={readOnly} className="grid min-w-0 gap-4">
            <legend className="sr-only">{isEdit ? c.riskTitle : c.riskNewTitle}</legend>

            {risk.data && (
              <div className="grid gap-1.5">
                <span className="text-sm font-medium">{c.fieldCode}</span>
                <output className="text-sm tabular-nums">{risk.data.code}</output>
              </div>
            )}

            <FormField
              control={form.control}
              name="processus"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldProcessus}</FormLabel>
                  <FormControl>
                    <NativeSelect
                      {...field}
                      disabled={readOnly || isEdit}
                      onChange={(e) => {
                        field.onChange(e);
                        form.setValue("objet_auditable", "");
                      }}
                    >
                      <option value="">{c.choose}</option>
                      {(processes.data?.results ?? []).map((pr) => (
                        <option key={pr.id} value={pr.id}>
                          {pr.code} - {pr.libelle}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="objet_auditable"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldObjet}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field} disabled={readOnly || !processusId}>
                      <option value="">{c.objetNone}</option>
                      {(tree.data ?? []).map((domaine) => (
                        <optgroup key={domaine.id} label={domaine.libelle}>
                          <option value={domaine.id}>{domaine.libelle}</option>
                          {domaine.operations.map((op) => (
                            <option key={op.id} value={op.id}>
                              {op.libelle}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="libelle"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldLibelleRisque}</FormLabel>
                  <FormControl>
                    <Input maxLength={500} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldDescription}</FormLabel>
                  <FormControl>
                    <Textarea rows={3} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 sm:grid-cols-3">
              {(["probabilite", "impact"] as const).map((name) => (
                <FormField
                  key={name}
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {name === "probabilite" ? c.fieldProbabilite : c.fieldImpact}
                      </FormLabel>
                      <FormControl>
                        <NativeSelect {...field}>
                          {SCALE.map((n) => (
                            <option key={n} value={n}>
                              {n}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))}
              <div className="grid content-start gap-2">
                <span className="text-sm font-medium">{c.preview}</span>
                <p className="flex items-center gap-2 text-sm" aria-live="polite">
                  <span className="font-medium tabular-nums">{`${c.previewScore} ${score} · ${NIVEAU_LABELS[niveau]}`}</span>
                  <RiskLevelBadge niveau={niveau} />
                </p>
              </div>
            </div>
            <p className="-mt-2 text-xs text-text-muted">{c.previewNote}</p>

            <FormField
              control={form.control}
              name="vulnerabilite"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldVulnerabilite}</FormLabel>
                  <FormControl>
                    <Textarea rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="reponse"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{c.fieldReponse}</FormLabel>
                    <FormControl>
                      <NativeSelect {...field}>
                        <option value="">{c.reponseNone}</option>
                        {(Object.keys(REPONSE_LABELS) as ReponseRisque[]).map((r) => (
                          <option key={r} value={r}>
                            {REPONSE_LABELS[r]}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="priorite"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{c.fieldPriorite}</FormLabel>
                    <FormControl>
                      <NativeSelect {...field} value={field.value || String(derivedPriorite)}>
                        {([1, 2, 3] as const).map((n) => (
                          <option key={n} value={String(n)}>
                            {PRIORITE_LABELS[n]}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="objectif_controle"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldObjectif}</FormLabel>
                  <FormControl>
                    <Textarea rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="dispositif_controle"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldDispositif}</FormLabel>
                  <FormControl>
                    <Textarea rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </fieldset>

          {general && (
            <p role="alert" className="text-sm text-destructive">
              {general}
            </p>
          )}
          {saved && (
            <p role="status" className="text-sm text-success-text">
              {c.savedOk}
            </p>
          )}

          {canEdit && (
            <div className="flex flex-wrap items-center gap-3 print:hidden">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? c.saving : fr.common.save}
              </Button>
              {isEdit && (
                <Button type="button" variant="destructive" onClick={() => setConfirmDelete(true)}>
                  {c.deleteRisk}
                </Button>
              )}
            </div>
          )}
        </form>
      </Form>

      {canEdit && isEdit && (
        <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{c.deleteTitle}</AlertDialogTitle>
              <AlertDialogDescription>{c.deleteWarning}</AlertDialogDescription>
            </AlertDialogHeader>
            {deleteError && (
              <p role="alert" className="text-sm text-destructive">
                {deleteError}
              </p>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel>{fr.common.cancel}</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={del.isPending}
                onClick={(e) => {
                  e.preventDefault();
                  void onDelete();
                }}
              >
                {del.isPending ? c.deleting : fr.common.delete}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
