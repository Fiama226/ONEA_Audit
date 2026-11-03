import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiDownload, apiFetch } from "@/api/client";
import { ApiError, isApiError } from "@/api/errors";
import { toQuery, type QueryParams } from "@/api/query";
import { missionKeys } from "@/features/missions/keys";
import { recommandationKeys } from "@/features/recommandations/keys";
import { fr } from "@/i18n/fr";
import { downloadBlob } from "@/lib/download";
import { communicationKeys } from "./keys";
import type {
  Destinataire,
  DestinataireInput,
  DestinataireUpdate,
  DocumentRapport,
  FormatRapport,
  Rapport,
  RapportAction,
  RapportActionPayload,
  RapportDiffuse,
  RapportModification,
  RapportProvisoire,
  ReponseRapport,
  ReponseRapportInput,
  TexteReponseRapport,
  SignatureRapport,
  TexteValidation,
} from "./types";

const BASE = "/api/v1";

/**
 * Règle d'invalidation du lot 7 : toute mutation de la communication ou du plan d'actions
 * invalide ses listes, le détail, les étapes et le suivi de la mission (lot 3), la synthèse
 * du plan et le rapport.
 */
export function invalidateLot7(
  client: QueryClient,
  missionId: string | undefined,
  ...extra: QueryKey[]
) {
  const keys: QueryKey[] = [
    communicationKeys.all,
    recommandationKeys.all,
    missionKeys.steps(missionId),
    [...missionKeys.all, "step"],
    missionKeys.detail(missionId),
    missionKeys.tracking(missionId),
    ...extra,
  ];
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

// ---- Rapport -----------------------------------------------------------------------------------

export function useReport(id: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.report(id),
    queryFn: () => apiFetch<Rapport>(`${BASE}/reports/${id}/`),
    enabled: id !== undefined,
  });
}

/** Version courante du rapport de la mission : la plus récente, ou `null` s'il n'existe pas encore. */
export function useMissionReport(missionId: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.missionReport(missionId),
    queryFn: async () => {
      const { results } = await fetchAllPages<Rapport>("reports", { mission: missionId });
      return results.reduce<Rapport | null>(
        (best, r) => (best === null || r.numero_version > best.numero_version ? r : best),
        null,
      );
    },
    enabled: missionId !== undefined,
  });
}

export function useCreateReport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId }: { missionId: string }) =>
      apiFetch<Rapport>(`${BASE}/reports/`, { method: "POST", json: { mission: missionId } }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useSaveReport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; missionId: string; data: RapportModification }) =>
      apiFetch<Rapport>(`${BASE}/reports/${id}/`, { method: "PATCH", json: data }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

/** Aperçu du rapport assemblé par le serveur (sections et contrôles de complétude). */
export function useReportPreview(id: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.preview(id),
    queryFn: () => apiFetch<Record<string, unknown>>(`${BASE}/reports/${id}/preview/`),
    enabled: id !== undefined,
  });
}

/** Transition du rapport ; « return » et « correct » exigent un motif, « validate » une confirmation. */
export function useReportAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      payload,
    }: {
      id: string;
      missionId: string;
      action: RapportAction;
      payload?: RapportActionPayload;
    }) =>
      apiFetch<Rapport | RapportDiffuse>(`${BASE}/reports/${id}/${action}/`, {
        method: "POST",
        json: payload ?? {},
      }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

/** Texte exact que le valideur confirme (affiché tel quel). */
export function useValidationText(id: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.validationText(id),
    queryFn: () => apiFetch<TexteValidation>(`${BASE}/reports/${id}/validation-text/`),
    enabled: id !== undefined,
  });
}

/** Signature électronique PAdES du rapport final : signataire, date et validité vérifiée. */
export function useReportSignature(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: communicationKeys.signature(id),
    queryFn: () => apiFetch<SignatureRapport>(`${BASE}/reports/${id}/signature/`),
    enabled: id !== undefined && enabled,
  });
}

// ---- Rapport provisoire et réponses des audités -----------------------------------------------

export function useDraftReports(rapportId: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.drafts(rapportId),
    queryFn: () => fetchAllPages<RapportProvisoire>("draft-reports", { rapport: rapportId }),
    enabled: rapportId !== undefined,
  });
}

export function useTransmitDraft() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, delaiJours }: { id: string; missionId: string; delaiJours: number }) =>
      apiFetch<RapportProvisoire>(`${BASE}/reports/${id}/transmit-draft/`, {
        method: "POST",
        json: { delai_jours: delaiJours },
      }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export type DraftResponseParams = { provisoire: string | undefined; constat?: string };

export function useDraftResponses(params: DraftResponseParams) {
  return useQuery({
    queryKey: communicationKeys.draftResponses(params),
    queryFn: () => fetchAllPages<ReponseRapport>("draft-report-responses", params),
    enabled: params.provisoire !== undefined,
    placeholderData: keepPreviousData,
  });
}

/** Réponse de l'audité à un constat du rapport provisoire ; la confirmation n'est jamais pré-cochée. */
export function useRespondDraft() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { missionId: string; data: ReponseRapportInput }) =>
      apiFetch<ReponseRapport>(`${BASE}/draft-report-responses/`, { method: "POST", json: data }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useDraftResponseText(
  provisoireId: string | undefined,
  constatId: string | undefined,
) {
  return useQuery({
    queryKey: communicationKeys.draftResponseText(provisoireId, constatId),
    queryFn: () =>
      apiFetch<TexteReponseRapport>(
        `${BASE}/draft-report-responses/texte/${toQuery({ provisoire: provisoireId, constat: constatId })}`,
      ),
    enabled: provisoireId !== undefined && constatId !== undefined,
  });
}

// ---- Diffusion --------------------------------------------------------------------------------

export function useRecipients(rapportId: string | undefined) {
  return useQuery({
    queryKey: communicationKeys.recipients(rapportId),
    queryFn: () => fetchAllPages<Destinataire>("report-recipients", { rapport: rapportId }),
    enabled: rapportId !== undefined,
  });
}

type SaveRecipient = { missionId: string } & (
  { id?: undefined; data: DestinataireInput } | { id: string; data: DestinataireUpdate }
);

export function useSaveRecipient() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveRecipient) =>
      vars.id === undefined
        ? apiFetch<Destinataire>(`${BASE}/report-recipients/`, { method: "POST", json: vars.data })
        : apiFetch<Destinataire>(`${BASE}/report-recipients/${vars.id}/`, {
            method: "PATCH",
            json: vars.data,
          }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

export function useRemoveRecipient() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/report-recipients/${id}/`, { method: "DELETE" }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

/** Remise hors plateforme : `le` est la date de remise (AAAA-MM-JJ). */
export function useMarkDelivered() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, le }: { id: string; missionId: string; le: string }) =>
      apiFetch<Destinataire>(`${BASE}/report-recipients/${id}/delivered/`, {
        method: "POST",
        json: { le },
      }),
    onSuccess: (_result, { missionId }) => invalidateLot7(client, missionId),
  });
}

/** Rapports diffusés visibles de l'utilisateur (sans filtre de mission). */
export function useDistributedReports(params: QueryParams = {}) {
  return useQuery({
    queryKey: communicationKeys.distributed(params),
    queryFn: () => fetchAllPages<RapportDiffuse>("reports", params),
    placeholderData: keepPreviousData,
  });
}

/** Télécharge le rapport ou sa note avec le jeton ; 409 : empreinte du fichier altérée. */
export async function downloadReport(
  id: string,
  format: FormatRapport,
  document: DocumentRapport = "rapport",
): Promise<void> {
  try {
    const { blob, filename } = await apiDownload(
      `${BASE}/reports/${id}/download/${toQuery({ format, document })}`,
    );
    downloadBlob(blob, filename);
  } catch (e) {
    if (isApiError(e) && e.status === 409) {
      throw new ApiError(409, fr.documents.integrityError);
    }
    throw e;
  }
}
