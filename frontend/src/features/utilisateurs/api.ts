import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { apiDownload, apiFetch } from "@/api/client";
import { toQuery, type QueryParams } from "@/api/query";
import type { components, operations } from "@/api/schema";
import { downloadBlob } from "@/lib/download";
import type {
  AccountAction,
  CompteUtilisateur,
  CreationCompteInput,
  Delegation,
  DelegationInput,
  MotDePasseTemporaire,
  ProfilInput,
  Role,
} from "./types";

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
  delegation: (id: number) => ["utilisateurs", "delegation", id] as QueryKey,
};

/**
 * Mutations qui renvoient un mot de passe temporaire : le résultat ne reste pas dans le cache
 * des mutations (gcTime 0, et `reset` par le composant à la fermeture) et n'est jamais copié
 * dans celui des requêtes. Seul le composant qui l'affiche le tient, le temps de l'affichage.
 */
const ONE_TIME_SECRET = { gcTime: 0 } as const;

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

export function useChangeRole() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) =>
      apiFetch<CompteUtilisateur>(`${BASE}/${id}/change-role/`, {
        method: "POST",
        json: { role },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

/** Création d'un agent ; le mot de passe temporaire éventuel n'est jamais mis en cache. */
export function useCreateAccount() {
  const client = useQueryClient();
  return useMutation({
    ...ONE_TIME_SECRET,
    mutationFn: (data: CreationCompteInput) =>
      apiFetch<MotDePasseTemporaire>(`${BASE}/`, { method: "POST", json: data }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

/** Réinitialisation du mot de passe ; même règle de non-mise en cache que la création. */
export function useResetPassword() {
  const client = useQueryClient();
  return useMutation({
    ...ONE_TIME_SECRET,
    mutationFn: ({ id, sendEmail }: { id: number; sendEmail: boolean }) =>
      apiFetch<MotDePasseTemporaire>(`${BASE}/${id}/reset-password/`, {
        method: "POST",
        json: { envoyer_courriel: sendEmail },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

/** Délégation d'un agent : lue et écrite par un administrateur seulement. */
export function useDelegation(id: number, enabled: boolean) {
  return useQuery({
    queryKey: userKeys.delegation(id),
    queryFn: () => apiFetch<Delegation>(`${BASE}/${id}/delegation/`),
    enabled,
  });
}

export function useSetDelegation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DelegationInput }) =>
      apiFetch<Delegation>(`${BASE}/${id}/delegation/`, { method: "PUT", json: data }),
    onSuccess: (delegation, { id }) => {
      client.setQueryData(userKeys.delegation(id), delegation);
      // Un agent devenu délégué est protégé des autres délégués : les fiches changent aussi.
      return client.invalidateQueries({ queryKey: userKeys.detail(id) });
    },
  });
}

export type ImportCsvVars = { file: File; dryRun: boolean; sendEmail: boolean };

export function useImportCsv() {
  const client = useQueryClient();
  return useMutation({
    // Le rapport porte l'identifiant du fichier des mots de passe : pas de rétention en cache.
    ...ONE_TIME_SECRET,
    mutationFn: ({ file, dryRun, sendEmail }: ImportCsvVars) => {
      const body = new FormData();
      body.append("fichier", file);
      body.append("dry_run", String(dryRun));
      body.append("envoyer_courriel", String(sendEmail));
      return apiFetch<S["RapportImport"]>(`${BASE}/import-csv/`, { method: "POST", body });
    },
    // Un import à blanc ne modifie rien : rien à invalider.
    onSuccess: (_report, vars) =>
      vars.dryRun ? undefined : client.invalidateQueries({ queryKey: userKeys.all }),
  });
}

/**
 * Télécharge le fichier des mots de passe d'un import : le serveur le détruit aussitôt (un
 * second appel répond 404). Rien n'est mis en cache.
 */
export async function downloadImportPasswords(fileId: string): Promise<void> {
  const { blob, filename } = await apiDownload(`${BASE}/import-passwords/${fileId}/`);
  downloadBlob(blob, filename);
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
