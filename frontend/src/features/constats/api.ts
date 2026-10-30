import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiFetch } from "@/api/client";
import type { QueryParams } from "@/api/query";
import { invalidateAccomplissement } from "../accomplissement/api";
import { constatKeys } from "./keys";
import type {
  Constat,
  ConstatAction,
  ConstatInput,
  ConstatUpdate,
  RecommandationListe,
  ReponseAudite,
  ReponseInput,
} from "./types";

const BASE = "/api/v1";

export function useFindings(params: { mission: string | undefined } & QueryParams) {
  return useQuery({
    queryKey: constatKeys.list(params.mission, params),
    queryFn: () => fetchAllPages<Constat>("findings", params),
    enabled: params.mission !== undefined,
    placeholderData: keepPreviousData,
  });
}

export function useFinding(id: string | undefined) {
  return useQuery({
    queryKey: constatKeys.detail(id),
    queryFn: () => apiFetch<Constat>(`${BASE}/findings/${id}/`),
    enabled: id !== undefined,
  });
}

type SaveFinding = { missionId: string } & (
  { id?: undefined; data: ConstatInput } | { id: string; data: ConstatUpdate }
);

/** Création ou mise à jour ; les causes et recommandations imbriquées remplacent les listes. */
export function useSaveFinding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveFinding) =>
      vars.id === undefined
        ? apiFetch<Constat>(`${BASE}/findings/`, { method: "POST", json: vars.data })
        : apiFetch<Constat>(`${BASE}/findings/${vars.id}/`, { method: "PATCH", json: vars.data }),
    onSuccess: (result, { missionId }) =>
      invalidateAccomplissement(
        client,
        missionId,
        constatKeys.mission(missionId),
        constatKeys.detail(result.id),
      ),
  });
}

export function useDeleteFinding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/findings/${id}/`, { method: "DELETE" }),
    onSuccess: async (_result, { id, missionId }) => {
      client.removeQueries({ queryKey: constatKeys.detail(id) });
      await invalidateAccomplissement(client, missionId, constatKeys.mission(missionId));
    },
  });
}

/** Transition d'un constat ; « return » exige un motif. */
export function useFindingAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      motif,
    }: {
      id: string;
      missionId: string;
      action: ConstatAction;
      motif?: string;
    }) =>
      apiFetch<Constat>(`${BASE}/findings/${id}/${action}/`, {
        method: "POST",
        json: motif === undefined ? {} : { motif },
      }),
    onSuccess: (_result, { id, missionId }) =>
      invalidateAccomplissement(
        client,
        missionId,
        constatKeys.mission(missionId),
        constatKeys.detail(id),
      ),
  });
}

export function useFindingResponses(constatId: string | undefined) {
  return useQuery({
    queryKey: constatKeys.responses(constatId),
    queryFn: () => fetchAllPages<ReponseAudite>("finding-responses", { constat: constatId }),
    enabled: constatId !== undefined,
  });
}

/** Réponse de l'audité (accord ou désaccord) ; la confirmation légale n'est jamais pré-cochée. */
export function useRespondFinding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { missionId: string; data: ReponseInput }) =>
      apiFetch<ReponseAudite>(`${BASE}/finding-responses/`, { method: "POST", json: data }),
    onSuccess: (_result, { missionId, data }) =>
      invalidateAccomplissement(
        client,
        missionId,
        constatKeys.mission(missionId),
        constatKeys.detail(data.constat),
        constatKeys.responses(data.constat),
      ),
  });
}

export function useRecommendations(missionId: string | undefined) {
  return useQuery({
    queryKey: constatKeys.recommendations(missionId),
    queryFn: () => fetchAllPages<RecommandationListe>("recommendations", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}
