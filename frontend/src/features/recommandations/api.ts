import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiFetch } from "@/api/client";
import { toQuery } from "@/api/query";
import { invalidateLot7 } from "../communication/api";
import { recommandationKeys } from "./keys";
import type {
  AcceptationInput,
  AcceptationRisque,
  ActionCorrective,
  ActionInput,
  ActionUpdate,
  EngagementPlanActions,
  SynthesePlan,
  TexteEngagement,
} from "./types";

const BASE = "/api/v1";

export type ActionParams = {
  mission: string | undefined;
  constat?: string;
  recommandation?: string;
  responsable?: number;
  mine?: string;
};

export type AcceptanceParams = { mission?: string; recommandation?: string };

export function useActions(params: ActionParams) {
  return useQuery({
    queryKey: recommandationKeys.actions(params),
    queryFn: () => fetchAllPages<ActionCorrective>("corrective-actions", params),
    enabled: params.mission !== undefined,
    placeholderData: keepPreviousData,
  });
}

type SaveAction = { missionId: string } & (
  { id?: undefined; data: ActionInput } | { id: string; data: ActionUpdate }
);

export function useSaveAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveAction) =>
      vars.id === undefined
        ? apiFetch<ActionCorrective>(`${BASE}/corrective-actions/`, {
            method: "POST",
            json: vars.data,
          })
        : apiFetch<ActionCorrective>(`${BASE}/corrective-actions/${vars.id}/`, {
            method: "PATCH",
            json: vars.data,
          }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useDeleteAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/corrective-actions/${id}/`, { method: "DELETE" }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useRiskAcceptances(params: AcceptanceParams) {
  return useQuery({
    queryKey: recommandationKeys.acceptances(params),
    queryFn: () => fetchAllPages<AcceptationRisque>("risk-acceptances", params),
    enabled: params.mission !== undefined || params.recommandation !== undefined,
  });
}

/** Acceptation du risque par l'audité : la confirmation n'est jamais pré-cochée. */
export function useAcceptRisk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { missionId: string; data: AcceptationInput }) =>
      apiFetch<AcceptationRisque>(`${BASE}/risk-acceptances/`, { method: "POST", json: data }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useWithdrawAcceptance() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/risk-acceptances/${id}/withdraw/`, { method: "POST" }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useCommitments(missionId: string | undefined) {
  return useQuery({
    queryKey: recommandationKeys.commitments(missionId),
    queryFn: () =>
      fetchAllPages<EngagementPlanActions>("action-plan-commitments", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

/** Engagement de l'audité sur son plan d'actions. */
export function useCommit() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId }: { missionId: string }) =>
      apiFetch<EngagementPlanActions>(`${BASE}/action-plan-commitments/`, {
        method: "POST",
        json: { mission: missionId, confirme: true },
      }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

/** Texte exact que l'audité confirme (affiché tel quel). */
export function useCommitmentText(missionId: string | undefined) {
  return useQuery({
    queryKey: recommandationKeys.commitmentText(missionId),
    queryFn: () =>
      apiFetch<TexteEngagement>(
        `${BASE}/action-plan-commitments/texte/${toQuery({ mission: missionId })}`,
      ),
    enabled: missionId !== undefined,
  });
}

export function useActionPlanSummary(missionId: string | undefined) {
  return useQuery({
    queryKey: recommandationKeys.summary(missionId),
    queryFn: () =>
      apiFetch<SynthesePlan>(`${BASE}/action-plans/summary/${toQuery({ mission: missionId })}`),
    enabled: missionId !== undefined,
  });
}
