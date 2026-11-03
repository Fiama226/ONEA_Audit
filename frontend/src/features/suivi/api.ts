import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { apiDownload, apiFetch } from "@/api/client";
import { ApiError, isApiError } from "@/api/errors";
import { uploadWithProgress } from "@/api/upload";
import { dashboardKeys } from "@/features/dashboard/keys";
import { missionKeys } from "@/features/missions/keys";
import { notificationKeys } from "@/features/notifications/keys";
import { fr } from "@/i18n/fr";
import { downloadBlob } from "@/lib/download";
import { suiviKeys } from "./keys";
import { TRANSITION_FIELD } from "./labels";
import { fetchAllFollowUp, suiviQuery, type SuiviQuery } from "./query";
import type {
  ActionParams,
  ActionSuivie,
  DecisionReport,
  DemandeReport,
  DemandeReportListe,
  EvenementAction,
  ExportKind,
  ExtensionInput,
  ExtensionParams,
  FormatExport,
  MissionACloturer,
  ReminderParams,
  Relance,
  MissionSuivie,
  PreuveMiseEnOeuvre,
  RecommandationSuivie,
  RecommendationParams,
  TransitionKind,
} from "./types";

const BASE = "/api/v1/follow-up";

/**
 * Règle d'invalidation du lot 8 : toute mutation du suivi invalide la fiche de l'action, les listes,
 * les tableaux de bord et le compteur de notifications non lues.
 */
export function invalidateSuivi(
  client: QueryClient,
  actionId?: string,
  ...extra: QueryKey[]
): Promise<unknown[]> {
  const keys: QueryKey[] = [
    ...(actionId ? [suiviKeys.action(actionId)] : []),
    suiviKeys.all,
    dashboardKeys.all,
    notificationKeys.unread,
    ...extra,
  ];
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

// ---- Lectures --------------------------------------------------------------------------------

export function useFollowUpActions(params: ActionParams = {}) {
  return useQuery({
    queryKey: suiviKeys.actions(params),
    queryFn: () => fetchAllFollowUp<ActionSuivie>("follow-up/actions", params),
    placeholderData: keepPreviousData,
  });
}

export function useFollowUpAction(id: string | undefined) {
  return useQuery({
    queryKey: suiviKeys.action(id),
    queryFn: () => apiFetch<ActionSuivie>(`${BASE}/actions/${id}/`),
    enabled: id !== undefined,
  });
}

export function useActionEvents(id: string | undefined) {
  return useQuery({
    queryKey: suiviKeys.events(id),
    queryFn: () => apiFetch<EvenementAction[]>(`${BASE}/actions/${id}/events/`),
    enabled: id !== undefined,
  });
}

export function useFollowUpRecommendations(params: RecommendationParams = {}) {
  return useQuery({
    queryKey: suiviKeys.recommendations(params),
    queryFn: () => fetchAllFollowUp<RecommandationSuivie>("follow-up/recommendations", params),
    placeholderData: keepPreviousData,
  });
}

// ---- Transitions, responsable -----------------------------------------------------------------

export type TransitionVars = {
  id: string;
  kind: TransitionKind;
  /** Commentaire, motif, justification ou texte selon la transition ; omis pour `start`. */
  text?: string;
  missionId?: string;
};

/** Transition du suivi : POST sur `/actions/{id}/{kind}/` ; renvoie l'action à jour. */
export function useActionTransition() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind, text }: TransitionVars) =>
      apiFetch<ActionSuivie>(`${BASE}/actions/${id}/${kind}/`, {
        method: "POST",
        json: text === undefined ? {} : { [TRANSITION_FIELD[kind]]: text },
      }),
    onSuccess: (_result, { id, missionId }) =>
      invalidateSuivi(
        client,
        id,
        suiviKeys.events(id),
        ...(missionId ? [missionKeys.detail(missionId)] : []),
      ),
  });
}

/** Changement de responsable (RAI uniquement). */
export function useChangeResponsible() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, responsable }: { id: string; responsable: number }) =>
      apiFetch<ActionSuivie>(`${BASE}/actions/${id}/`, {
        method: "PATCH",
        json: { responsable },
      }),
    onSuccess: (_result, { id }) => invalidateSuivi(client, id, suiviKeys.events(id)),
  });
}

// ---- Preuves de mise en œuvre -----------------------------------------------------------------

export function useImplementationEvidence(actionId: string | undefined) {
  return useQuery({
    queryKey: suiviKeys.evidence(actionId),
    queryFn: () => fetchAllFollowUp<PreuveMiseEnOeuvre>("follow-up/evidence", { action: actionId }),
    enabled: actionId !== undefined,
  });
}

export type UploadEvidenceVars = {
  actionId: string;
  file: File;
  libelle: string;
  description?: string;
  commentaire?: string;
  onProgress: (ratio: number) => void;
  signal?: AbortSignal;
};

export function useUploadImplementationEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      actionId,
      file,
      libelle,
      description,
      commentaire,
      onProgress,
      signal,
    }: UploadEvidenceVars) => {
      const form = new FormData();
      form.append("action", actionId);
      form.append("fichier", file);
      form.append("libelle", libelle);
      form.append("description", description ?? "");
      if (commentaire) form.append("commentaire", commentaire);
      return uploadWithProgress<PreuveMiseEnOeuvre>(
        `${BASE}/evidence/${suiviQuery({ action: actionId })}`,
        form,
        onProgress,
        signal,
      );
    },
    onSuccess: (_result, { actionId }) =>
      invalidateSuivi(client, actionId, suiviKeys.evidence(actionId), suiviKeys.events(actionId)),
  });
}

export function useUpdateImplementationEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      actionId: string;
      data: { libelle?: string; description?: string };
    }) => apiFetch<PreuveMiseEnOeuvre>(`${BASE}/evidence/${id}/`, { method: "PATCH", json: data }),
    onSuccess: (_result, { actionId }) =>
      invalidateSuivi(client, actionId, suiviKeys.evidence(actionId)),
  });
}

export function useRemoveImplementationEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; actionId: string }) =>
      apiFetch<undefined>(`${BASE}/evidence/${id}/`, { method: "DELETE" }),
    onSuccess: (_result, { actionId }) =>
      invalidateSuivi(client, actionId, suiviKeys.evidence(actionId), suiviKeys.events(actionId)),
  });
}

// ---- Reports d'échéance ----------------------------------------------------------------------

export function useExtensionRequests(params: ExtensionParams = {}) {
  return useQuery({
    queryKey: suiviKeys.extensions(params),
    queryFn: () => fetchAllFollowUp<DemandeReport>("follow-up/extension-requests", params),
    placeholderData: keepPreviousData,
  });
}

/** Journal des reports (RAI) : lignes enrichies de la mission et de l'action. */
export function useExtensionJournal(params: ExtensionParams = {}) {
  return useQuery({
    queryKey: suiviKeys.extensions({ journal: true, ...params }),
    queryFn: () => fetchAllFollowUp<DemandeReportListe>("follow-up/extension-requests", params),
    placeholderData: keepPreviousData,
  });
}

/** Journal des relances (RAI) ; `statut` reprend les filtres de la file de décisions. */
export function useReminders(params: ReminderParams = {}) {
  return useQuery({
    queryKey: suiviKeys.reminders(params),
    queryFn: () => fetchAllFollowUp<Relance>("reminders", params),
    placeholderData: keepPreviousData,
  });
}

export function useRequestExtension() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: ExtensionInput) =>
      apiFetch<DemandeReport>(`${BASE}/extension-requests/`, { method: "POST", json: data }),
    onSuccess: (_result, { action }) =>
      invalidateSuivi(client, action, suiviKeys.extensions(), suiviKeys.events(action)),
  });
}

/** Décision du RAI sur un report ; le commentaire est obligatoire pour un refus. */
export function useDecideExtension() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      commentaire,
    }: {
      id: string;
      decision: DecisionReport;
      commentaire: string;
      actionId?: string;
    }) =>
      apiFetch<DemandeReport>(`${BASE}/extension-requests/${id}/${decision}/`, {
        method: "POST",
        json: { commentaire },
      }),
    onSuccess: (_result, { actionId }) =>
      invalidateSuivi(
        client,
        actionId,
        suiviKeys.extensions(),
        ...(actionId ? [suiviKeys.events(actionId)] : []),
      ),
  });
}

// ---- Clôture de mission ----------------------------------------------------------------------

export function useMissionsToClose() {
  return useQuery({
    queryKey: suiviKeys.missionsToClose(),
    queryFn: () => fetchAllFollowUp<MissionACloturer>("follow-up/missions"),
  });
}

export function useCloseMission() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, commentaire }: { id: string; commentaire?: string }) =>
      apiFetch<MissionSuivie>(`${BASE}/missions/${id}/close/`, {
        method: "POST",
        json: commentaire ? { commentaire } : {},
      }),
    onSuccess: (_result, { id }) =>
      Promise.all([
        invalidateSuivi(client, undefined, suiviKeys.missionsToClose()),
        client.invalidateQueries({ queryKey: missionKeys.detail(id) }),
        client.invalidateQueries({ queryKey: missionKeys.lists() }),
      ]),
  });
}

// ---- Exports et téléchargements --------------------------------------------------------------

/** Exporte le registre (actions ou recommandations) avec les filtres courants. */
export async function downloadFollowUpExport(
  kind: ExportKind,
  params: ActionParams | RecommendationParams,
  format: FormatExport,
): Promise<void> {
  // Pagination et tri n'ont pas de sens pour un export : seuls les filtres sont transmis.
  const filters: SuiviQuery = { ...params, page: undefined, page_size: undefined };
  const { blob, filename } = await apiDownload(
    `${BASE}/${kind}/export/${suiviQuery({ ...filters, ordering: undefined, format })}`,
  );
  downloadBlob(blob, filename);
}

/** Télécharge une preuve ; 409 : empreinte du fichier stocké altérée. */
export async function downloadImplementationEvidence(id: string, filename?: string): Promise<void> {
  try {
    const result = await apiDownload(`${BASE}/evidence/${id}/download/`);
    downloadBlob(result.blob, filename ?? result.filename);
  } catch (e) {
    if (isApiError(e) && e.status === 409) throw new ApiError(409, fr.suivi.evidenceAltered);
    throw e;
  }
}
