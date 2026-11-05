import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { toQuery } from "@/api/query";
import type { components } from "@/api/schema";

type S = components["schemas"];

export type GovernanceRule = S["RegleGouvernance"];
export type AuditLogEntry = S["AuditLog"];
export type PendingAcceptance = S["AcceptationAValider"];
export type PendingWaiver = S["EtapeADeroger"];

const BASE = "/api/v1";

export const governanceKeys = {
  all: ["gouvernance"] as const,
  rules: () => [...governanceKeys.all, "rules"] as const,
  journal: (params: JournalParams) => [...governanceKeys.all, "journal", params] as const,
  acceptances: () => [...governanceKeys.all, "acceptances"] as const,
  waivers: () => [...governanceKeys.all, "waivers"] as const,
};

export function useGovernanceRules() {
  return useQuery({
    queryKey: governanceKeys.rules(),
    queryFn: () => apiFetch<GovernanceRule[]>(`${BASE}/governance-rules/`),
  });
}

export function useUpdateGovernanceRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      key,
      valeur,
      motif,
    }: {
      key: string;
      valeur: Record<string, unknown>;
      motif: string;
    }) =>
      apiFetch<GovernanceRule>(`${BASE}/governance-rules/${encodeURIComponent(key)}/`, {
        method: "PATCH",
        json: { valeur, motif },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: governanceKeys.all }),
  });
}

export type JournalParams = {
  categorie?: "gouvernance";
  date_from?: string;
  date_to?: string;
  page?: number;
};

export function useAuditJournal(params: JournalParams) {
  return useQuery({
    queryKey: governanceKeys.journal(params),
    queryFn: () => apiFetch<S["PaginatedAuditLogList"]>(`${BASE}/audit-log/${toQuery(params)}`),
    placeholderData: keepPreviousData,
  });
}

export function usePendingAcceptances(enabled: boolean) {
  return useQuery({
    queryKey: governanceKeys.acceptances(),
    queryFn: () => apiFetch<PendingAcceptance[]>(`${BASE}/risk-acceptance-validations/`),
    enabled,
  });
}

export function useDecideAcceptance() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      motif,
      reference_conseil,
    }: {
      id: string;
      decision: "VALIDEE" | "REFUSEE";
      motif: string;
      reference_conseil?: string;
    }) =>
      apiFetch<void>(`${BASE}/risk-acceptance-validations/${id}/decide/`, {
        method: "POST",
        json: { decision, motif, reference_conseil: reference_conseil ?? "" },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: governanceKeys.acceptances() }),
  });
}

export function usePendingWaivers(enabled: boolean) {
  return useQuery({
    queryKey: governanceKeys.waivers(),
    queryFn: () => apiFetch<PendingWaiver[]>(`${BASE}/auditee-response-waivers/`),
    enabled,
  });
}

export function useWaive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ stepId, motif }: { stepId: string; motif: string }) =>
      apiFetch<void>(`${BASE}/auditee-response-waivers/${stepId}/waive/`, {
        method: "POST",
        json: { motif },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: governanceKeys.waivers() }),
  });
}
