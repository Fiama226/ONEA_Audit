import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { isApiError } from "@/api/errors";
import { toQuery, type QueryParams } from "@/api/query";
import type { components, operations } from "@/api/schema";
import type { AccountAction, CompteUtilisateur, ProfilInput } from "./types";

type S = components["schemas"];

export type UserAccountParams = NonNullable<
  operations["v1_user_accounts_list"]["parameters"]["query"]
>;

const BASE = "/api/v1/user-accounts";

/** `toQuery` n'accepte pas les booléens : ils sont sérialisés en « true » / « false ». */
function listQuery(params: UserAccountParams): QueryParams {
  return Object.fromEntries(
    Object.entries(params).map(([k, v]) => [k, typeof v === "boolean" ? String(v) : v]),
  );
}

/** Clés TanStack Query ; `all` est aussi le préfixe de l'historique (history.ts) : tout est invalidé ensemble. */
export const userKeys = {
  all: ["utilisateurs"] as QueryKey,
  list: (params: UserAccountParams) => ["utilisateurs", "list", params] as QueryKey,
  detail: (id: number) => ["utilisateurs", "detail", id] as QueryKey,
  directory: (q: string) => ["utilisateurs", "directory", q] as QueryKey,
};

export function useUserAccounts(params: UserAccountParams = {}) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () =>
      apiFetch<S["PaginatedCompteUtilisateurListeList"]>(`${BASE}/${toQuery(listQuery(params))}`),
    placeholderData: keepPreviousData,
  });
}

export function useUserAccount(id: number) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => apiFetch<CompteUtilisateur>(`${BASE}/${id}/`),
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProfilInput }) =>
      apiFetch<CompteUtilisateur>(`${BASE}/${id}/`, { method: "PATCH", json: data }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export type AccountActionVars = { id: number; action: AccountAction; motif?: string };

export function useAccountAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, motif }: AccountActionVars) =>
      apiFetch<CompteUtilisateur>(`${BASE}/${id}/${action}/`, {
        method: "POST",
        ...(motif !== undefined ? { json: { motif } } : {}),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useDirectorySearch(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: userKeys.directory(term),
    queryFn: () =>
      apiFetch<S["EntreeAnnuaire"][]>(`${BASE}/directory-search/${toQuery({ q: term })}`),
    enabled: term.length >= 2,
    // Une erreur HTTP (ex. 503 Keycloak) n'est pas retentée : le message s'affiche tout de suite
    // et l'annuaire ne reçoit pas 4 appels par recherche. Seule une erreur réseau l'est.
    retry: (count, error) => !(isApiError(error) && error.status > 0) && count < 2,
  });
}

export function useImportDirectory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: { keycloak_ids: string[] }) =>
      apiFetch<S["RapportImport"]>(`${BASE}/import-directory/`, { method: "POST", json: data }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useImportCsv() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, dryRun }: { file: File; dryRun: boolean }) => {
      const body = new FormData();
      body.append("fichier", file);
      body.append("dry_run", String(dryRun));
      return apiFetch<S["RapportImport"]>(`${BASE}/import-csv/`, { method: "POST", body });
    },
    // Un import à blanc ne modifie rien : rien à invalider.
    onSuccess: (_report, vars) =>
      vars.dryRun ? undefined : client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

/** Taille de page demandée ; au-delà, la liste des directions est signalée incomplète. */
const DIRECTION_PAGE_SIZE = 200;

/** Directions pour les sélecteurs de profil (autonome vis-à-vis du lot Référentiel). */
export function useDirectionOptions() {
  const query = useQuery({
    queryKey: ["directions", "options"] as QueryKey,
    queryFn: () =>
      apiFetch<S["PaginatedDirectionList"]>(
        `/api/v1/directions/${toQuery({ page_size: DIRECTION_PAGE_SIZE, ordering: "code" })}`,
      ),
    staleTime: 5 * 60 * 1000,
  });
  return {
    ...query,
    options: query.data?.results ?? [],
    incomplete: (query.data?.count ?? 0) > DIRECTION_PAGE_SIZE,
  };
}
