import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import type { components, operations } from "@/api/schema";
import { apiDownload, apiFetch, DEFAULT_DOWNLOAD_NAME } from "@/api/client";
import { toQuery } from "@/api/query";
import { downloadBlob } from "@/lib/download";
import { fetchAllPages } from "./shared";
import type {
  AuditPlan,
  AuditPlanInput,
  AuditPlanLine,
  AuditPlanLineInput,
  AuditPlanSummary,
} from "./types";

type S = components["schemas"];
type Query<K extends keyof operations> = NonNullable<operations[K]["parameters"]["query"]>;

export type PlanParams = Query<"v1_audit_plans_list">;
export type LineParams = Omit<
  Query<"v1_audit_plan_lines_list">,
  "page" | "page_size" | "programme"
>;

const BASE = "/api/v1";
const ROOT = ["programmation"] as const;

/** Clés TanStack Query ; appelées sans argument, elles servent de préfixe d'invalidation. */
export const planKeys = {
  all: ROOT as QueryKey,
  plans: (params?: PlanParams) =>
    (params ? [...ROOT, "plans", "list", params] : [...ROOT, "plans"]) as QueryKey,
  plan: (id: string | undefined) => [...ROOT, "plans", "detail", id] as QueryKey,
  summary: (id: string | undefined) => [...ROOT, "plans", "summary", id] as QueryKey,
  lines: (planId?: string, params?: LineParams) =>
    (planId === undefined
      ? [...ROOT, "lines"]
      : [...ROOT, "lines", "list", planId, params ?? {}]) as QueryKey,
  line: (id: string | undefined) => [...ROOT, "lines", "detail", id] as QueryKey,
};

function invalidate(client: QueryClient, ...keys: QueryKey[]): Promise<unknown> {
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

// ---- Programmes ----------------------------------------------------------------------------

export function useAuditPlans(params: PlanParams = {}) {
  return useQuery({
    queryKey: planKeys.plans(params),
    queryFn: () =>
      apiFetch<S["PaginatedProgrammeAnnuelList"]>(`${BASE}/audit-plans/${toQuery(params)}`),
  });
}

export function useAuditPlan(id: string | undefined) {
  return useQuery({
    queryKey: planKeys.plan(id),
    queryFn: () => apiFetch<AuditPlan>(`${BASE}/audit-plans/${id}/`),
    enabled: id !== undefined,
  });
}

export function useCreateAuditPlan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: AuditPlanInput) =>
      apiFetch<AuditPlan>(`${BASE}/audit-plans/`, { method: "POST", json: data }),
    onSuccess: () => invalidate(client, planKeys.plans()),
  });
}

export function useUpdateAuditPlan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AuditPlanInput> }) =>
      apiFetch<AuditPlan>(`${BASE}/audit-plans/${id}/`, { method: "PATCH", json: data }),
    onSuccess: () => invalidate(client, planKeys.plans()),
  });
}

export function useDeleteAuditPlan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<undefined>(`${BASE}/audit-plans/${id}/`, { method: "DELETE" }),
    // Le programme n'existe plus : seul le rafraîchissement des listes a un sens (relire son
    // détail ou sa synthèse donnerait 404). Voir `useForgetAuditPlan` pour le retrait du cache.
    onSuccess: () => invalidate(client, [...ROOT, "plans", "list"]),
  });
}

/**
 * Retire du cache le détail, la synthèse et les lignes d'un programme supprimé. À appeler une fois
 * que plus aucune page ne les observe, sinon l'observateur les relirait (404).
 */
export function useForgetAuditPlan() {
  const client = useQueryClient();
  return (id: string) => {
    client.removeQueries({ queryKey: planKeys.plan(id) });
    client.removeQueries({ queryKey: planKeys.summary(id) });
    client.removeQueries({ queryKey: planKeys.lines(id) });
  };
}

/** Tous les programmes (toutes les pages) : sert à choisir une année encore libre. */
export function useAllAuditPlans(enabled = true) {
  return useQuery({
    queryKey: [...ROOT, "plans", "list", "all"] as QueryKey,
    queryFn: () => fetchAllPages<AuditPlan>("audit-plans"),
    enabled,
  });
}

export function useValidateAuditPlan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<AuditPlan>(`${BASE}/audit-plans/${id}/validate/`, { method: "POST" }),
    onSuccess: () => invalidate(client, planKeys.all),
  });
}

export function useAuditPlanSummary(id: string | undefined) {
  return useQuery({
    queryKey: planKeys.summary(id),
    queryFn: () => apiFetch<AuditPlanSummary>(`${BASE}/audit-plans/${id}/summary/`),
    enabled: id !== undefined,
  });
}

/** Exporte un programme en CSV ou Excel et déclenche l'enregistrement du fichier. */
export async function exportAuditPlan(id: string, type: "csv" | "xlsx" | "pdf"): Promise<void> {
  const { blob, filename } = await apiDownload(
    `${BASE}/audit-plans/${id}/export/${toQuery({ type })}`,
  );
  downloadBlob(blob, filename === DEFAULT_DOWNLOAD_NAME ? `programme-annuel.${type}` : filename);
}

// ---- Lignes (missions prévues) -------------------------------------------------------------

/** Toutes les lignes d'un programme (toutes les pages). */
export function useAuditPlanLines(planId: string | undefined, params: LineParams = {}) {
  return useQuery({
    queryKey: planKeys.lines(planId, params),
    queryFn: () =>
      fetchAllPages<AuditPlanLine>("audit-plan-lines", { ...params, programme: planId }),
    enabled: planId !== undefined,
  });
}

export function useAuditPlanLine(id: string | undefined) {
  return useQuery({
    queryKey: planKeys.line(id),
    queryFn: () => apiFetch<AuditPlanLine>(`${BASE}/audit-plan-lines/${id}/`),
    enabled: id !== undefined,
  });
}

/** Une mutation de ligne change les lignes, les compteurs du programme et sa synthèse. */
function invalidateLines(client: QueryClient) {
  return invalidate(
    client,
    planKeys.lines(),
    [...ROOT, "plans", "detail"],
    [...ROOT, "plans", "summary"],
    [...ROOT, "plans", "list"],
  );
}

export type SaveLineVars =
  { id?: undefined; data: AuditPlanLineInput } | { id: string; data: Partial<AuditPlanLineInput> };

export function useSaveAuditPlanLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveLineVars) =>
      vars.id === undefined
        ? apiFetch<AuditPlanLine>(`${BASE}/audit-plan-lines/`, { method: "POST", json: vars.data })
        : apiFetch<AuditPlanLine>(`${BASE}/audit-plan-lines/${vars.id}/`, {
            method: "PATCH",
            json: vars.data,
          }),
    onSuccess: () => invalidateLines(client),
  });
}

export function useDeleteAuditPlanLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<undefined>(`${BASE}/audit-plan-lines/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidateLines(client),
  });
}
