import {
  useMutation,
  keepPreviousData,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import type { components, operations } from "@/api/schema";
import { apiDownload, apiFetch, DEFAULT_DOWNLOAD_NAME } from "@/api/client";
import { fetchAllPages } from "@/api/allPages";
import { toQuery } from "@/api/query";
import { downloadBlob } from "@/lib/download";
import type {
  CartographieVersion,
  CartographieVersionInput,
  Comparaison,
  Direction,
  DirectionInput,
  DomaineArbre,
  Matrice,
  ObjetAuditable,
  ObjetAuditableInput,
  Processus,
  ProcessusInput,
  Risque,
  RisqueInput,
} from "./types";

type S = components["schemas"];
type Query<K extends keyof operations> = NonNullable<operations[K]["parameters"]["query"]>;

export type DirectionParams = Query<"v1_directions_list">;
export type ProcessParams = Query<"v1_processes_list">;
export type RiskMapParams = Query<"v1_risk_maps_list">;
export type RiskParams = Query<"v1_risks_list">;

const BASE = "/api/v1";

const ROOT = ["referentiel"] as const;
const family = (name: string) => ({
  all: [...ROOT, name] as QueryKey,
  list: (params: object) => [...ROOT, name, "list", params] as QueryKey,
  detail: (id: string | undefined) => [...ROOT, name, "detail", id] as QueryKey,
});
const f = {
  directions: family("directions"),
  processes: family("processes"),
  tree: family("auditable-tree"),
  objects: family("auditable-objects"),
  riskMaps: family("risk-maps"),
  risks: family("risks"),
  matrices: family("matrices"),
  comparisons: family("comparisons"),
};

/** Clés TanStack Query du Référentiel ; appelées sans argument, elles servent de préfixe d'invalidation. */
export const referentielKeys = {
  all: ROOT as QueryKey,
  directions: (params?: DirectionParams) => (params ? f.directions.list(params) : f.directions.all),
  processes: (params?: ProcessParams) => (params ? f.processes.list(params) : f.processes.all),
  process: (id: string | undefined) => f.processes.detail(id),
  auditableTree: (processId?: string) =>
    processId === undefined ? f.tree.all : f.tree.detail(processId),
  auditableObjects: () => f.objects.all,
  riskMaps: (params?: RiskMapParams) => (params ? f.riskMaps.list(params) : f.riskMaps.all),
  riskMap: (id: string | undefined) => f.riskMaps.detail(id),
  risks: (params?: RiskParams) => (params ? f.risks.list(params) : f.risks.all),
  risk: (id: string | undefined) => f.risks.detail(id),
  matrices: () => f.matrices.all,
  matrix: (id: string | undefined) => f.matrices.detail(id),
  comparison: (id: string | undefined, withId: string | undefined) =>
    [...f.comparisons.all, id, withId] as QueryKey,
};

/** Création (sans id) ou modification partielle (avec id). */
export type SaveVars<T> = { id?: undefined; data: T } | { id: string; data: Partial<T> };

function save<T, R>(resource: string, vars: SaveVars<T>): Promise<R> {
  return vars.id === undefined
    ? apiFetch<R>(`${BASE}/${resource}/`, { method: "POST", json: vars.data })
    : apiFetch<R>(`${BASE}/${resource}/${vars.id}/`, { method: "PATCH", json: vars.data });
}

function remove(resource: string, id: string): Promise<void> {
  return apiFetch<undefined>(`${BASE}/${resource}/${id}/`, { method: "DELETE" });
}

function invalidate(client: QueryClient, ...keys: QueryKey[]): Promise<unknown> {
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

/** Enregistrer ou supprimer un risque change aussi la matrice et le nombre de risques des versions. */
const riskKeys = () => [f.risks.all, f.matrices.all, f.riskMaps.all, f.comparisons.all];

// ---- Directions ----------------------------------------------------------------------------

export function useDirections(params: DirectionParams = {}) {
  return useQuery({
    queryKey: referentielKeys.directions(params),
    queryFn: () => apiFetch<S["PaginatedDirectionList"]>(`${BASE}/directions/${toQuery(params)}`),
  });
}

export function useSaveDirection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<DirectionInput>) =>
      save<DirectionInput, Direction>("directions", vars),
    onSuccess: () => invalidate(client, f.directions.all, f.processes.all),
  });
}

export function useDeleteDirection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("directions", id),
    onSuccess: () => invalidate(client, f.directions.all, f.processes.all),
  });
}

// ---- Processus -----------------------------------------------------------------------------

export function useProcesses(params: ProcessParams = {}) {
  return useQuery({
    queryKey: referentielKeys.processes(params),
    queryFn: () => apiFetch<S["PaginatedProcessusList"]>(`${BASE}/processes/${toQuery(params)}`),
  });
}

export function useProcess(id: string | undefined) {
  return useQuery({
    queryKey: referentielKeys.process(id),
    queryFn: () => apiFetch<Processus>(`${BASE}/processes/${id}/`),
    enabled: id !== undefined,
  });
}

export function useSaveProcess() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<ProcessusInput>) =>
      save<ProcessusInput, Processus>("processes", vars),
    onSuccess: () => invalidate(client, f.processes.all, f.tree.all),
  });
}

export function useDeleteProcess() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("processes", id),
    onSuccess: () => invalidate(client, f.processes.all, f.tree.all),
  });
}

// ---- Objets auditables ---------------------------------------------------------------------

/** Arbre domaines → opérations d'un processus (désactivé tant que le processus n'est pas choisi). */
export function useAuditableTree(processId?: string) {
  return useQuery({
    queryKey: referentielKeys.auditableTree(processId),
    queryFn: () =>
      apiFetch<DomaineArbre[]>(
        `${BASE}/auditable-objects/tree/${toQuery({ processus: processId })}`,
      ),
    enabled: processId !== undefined && processId !== "",
  });
}

export function useSaveAuditableObject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<ObjetAuditableInput>) =>
      save<ObjetAuditableInput, ObjetAuditable>("auditable-objects", vars),
    onSuccess: () => invalidate(client, f.tree.all, f.objects.all, f.risks.all),
  });
}

export function useDeleteAuditableObject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("auditable-objects", id),
    onSuccess: () => invalidate(client, f.tree.all, f.objects.all, f.risks.all),
  });
}

// ---- Cartographies (versions) --------------------------------------------------------------

export function useRiskMaps(params: RiskMapParams = {}) {
  return useQuery({
    queryKey: referentielKeys.riskMaps(params),
    queryFn: () =>
      apiFetch<S["PaginatedCartographieVersionList"]>(`${BASE}/risk-maps/${toQuery(params)}`),
  });
}

export function useRiskMap(id: string | undefined) {
  return useQuery({
    queryKey: referentielKeys.riskMap(id),
    queryFn: () => apiFetch<CartographieVersion>(`${BASE}/risk-maps/${id}/`),
    enabled: id !== undefined,
  });
}

export function useCreateRiskMap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: CartographieVersionInput) =>
      apiFetch<CartographieVersion>(`${BASE}/risk-maps/`, { method: "POST", json: data }),
    onSuccess: () => invalidate(client, f.riskMaps.all),
  });
}

export function useUpdateRiskMap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CartographieVersionInput> }) =>
      apiFetch<CartographieVersion>(`${BASE}/risk-maps/${id}/`, { method: "PATCH", json: data }),
    onSuccess: () => invalidate(client, f.riskMaps.all, f.risks.all, f.comparisons.all),
  });
}

export function useValidateRiskMap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<CartographieVersion>(`${BASE}/risk-maps/${id}/validate/`, { method: "POST" }),
    onSuccess: () => invalidate(client, ...riskKeys()),
  });
}

export function useDeleteRiskMap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("risk-maps", id),
    onSuccess: () => invalidate(client, ...riskKeys()),
  });
}

export function useRiskMatrix(id: string | undefined) {
  return useQuery({
    queryKey: referentielKeys.matrix(id),
    queryFn: () => apiFetch<Matrice>(`${BASE}/risk-maps/${id}/matrix/`),
    enabled: id !== undefined,
  });
}

/**
 * Comparaison côté serveur : `id` (dans l'URL) est la version de référence et `withId` la cible.
 * `ajoutes` = risques présents dans la cible seulement, `retires` = dans la référence seulement,
 * `changements[champ] = [valeur de la référence, valeur de la cible]`. Inactive sans `withId`.
 */
export function useRiskMapComparison(id: string | undefined, withId?: string) {
  return useQuery({
    queryKey: referentielKeys.comparison(id, withId),
    queryFn: () =>
      apiFetch<Comparaison>(`${BASE}/risk-maps/${id}/compare/${toQuery({ with: withId })}`),
    enabled: id !== undefined && withId !== undefined && withId !== "",
  });
}

/** Exporte une version en CSV ou Excel et déclenche l'enregistrement du fichier. */
export async function exportRiskMap(id: string, type: "csv" | "xlsx"): Promise<void> {
  const { blob, filename } = await apiDownload(
    `${BASE}/risk-maps/${id}/export/${toQuery({ type })}`,
  );
  downloadBlob(blob, filename === DEFAULT_DOWNLOAD_NAME ? `cartographie.${type}` : filename);
}

// ---- Risques -------------------------------------------------------------------------------

export function useRisks(params: RiskParams = {}) {
  return useQuery({
    queryKey: referentielKeys.risks(params),
    queryFn: () => apiFetch<S["PaginatedRisqueList"]>(`${BASE}/risks/${toQuery(params)}`),
    // Garde les lignes affichées pendant le changement de page ou de filtre (pas de clignotement),
    // mais jamais celles d'une autre version (cartographie) sous le nouvel en-tête.
    placeholderData: (previous, previousQuery) => {
      const previousParams = previousQuery?.queryKey[3] as RiskParams | undefined;
      return previousParams?.version === params.version ? keepPreviousData(previous) : undefined;
    },
  });
}

/** Charge toutes les pages d'une liste de risques (impression complète). */
export async function fetchAllRisks(params: RiskParams): Promise<Risque[]> {
  // `fetchAllPages` impose lui-même la pagination (page, page_size).
  return (
    await fetchAllPages<Risque>("risks", { ...params, page: undefined, page_size: undefined })
  ).results;
}

export function useRisk(id: string | undefined) {
  return useQuery({
    queryKey: referentielKeys.risk(id),
    queryFn: () => apiFetch<Risque>(`${BASE}/risks/${id}/`),
    enabled: id !== undefined,
  });
}

export function useSaveRisk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<RisqueInput>) => save<RisqueInput, Risque>("risks", vars),
    onSuccess: () => invalidate(client, ...riskKeys()),
  });
}

export function useDeleteRisk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("risks", id),
    onSuccess: () => invalidate(client, ...riskKeys()),
  });
}
