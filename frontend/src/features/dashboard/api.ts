import { useQuery } from "@tanstack/react-query";
import { apiDownload, apiFetch } from "@/api/client";
import type { components } from "@/api/schema";
import { toQuery } from "@/api/query";
import { downloadBlob } from "@/lib/download";
import { dashboardKeys } from "./keys";

type S = components["schemas"];
export type TableauRai = S["TableauRai"];
export type TableauDg = S["TableauDg"];
export type TableauAuditeur = S["TableauAuditeur"];
export type TableauAudite = S["TableauAudite"];

const BASE = "/api/v1/dashboards";

export function useDashboardRai(annee?: number) {
  return useQuery({
    queryKey: dashboardKeys.rai(annee),
    queryFn: () => apiFetch<TableauRai>(`${BASE}/rai/${toQuery({ annee })}`),
  });
}

export function useDashboardDg(annee?: number) {
  return useQuery({
    queryKey: dashboardKeys.dg(annee),
    queryFn: () => apiFetch<TableauDg>(`${BASE}/dg/${toQuery({ annee })}`),
  });
}

export function useDashboardAuditor() {
  return useQuery({
    queryKey: dashboardKeys.auditor(),
    queryFn: () => apiFetch<TableauAuditeur>(`${BASE}/auditor/`),
  });
}

export function useDashboardAuditee() {
  return useQuery({
    queryKey: dashboardKeys.auditee(),
    queryFn: () => apiFetch<TableauAudite>(`${BASE}/auditee/`),
  });
}

/** Exporte les taux de mise en œuvre (CSV ou Excel) d'une année. */
export async function downloadImplementationRates(
  annee: number | undefined,
  format: "csv" | "xlsx",
): Promise<void> {
  const { blob, filename } = await apiDownload(
    `${BASE}/implementation-rates/export/${toQuery({ annee, format })}`,
  );
  downloadBlob(blob, filename);
}
