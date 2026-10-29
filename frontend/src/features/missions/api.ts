import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiFetch } from "@/api/client";
import { toQuery } from "@/api/query";
import type { components, operations } from "@/api/schema";
import { missionKeys } from "./keys";
import type {
  Affectation,
  AffectationInput,
  Declaration,
  Entretien,
  EntretienInput,
  Etape,
  EtapeInput,
  FicheSuivi,
  MatriceMission,
  Mission,
  MissionInput,
  Reunion,
  ReunionInput,
  RisqueMission,
  RisqueMissionInput,
  UtilisateurResume,
} from "./types";

export { missionKeys };

type S = components["schemas"];
type Query<K extends keyof operations> = NonNullable<operations[K]["parameters"]["query"]>;

export type MissionParams = Query<"v1_missions_list">;
export type UserParams = Query<"v1_users_list">;
export type InterviewParams = Query<"v1_interviews_list">;
export type DeclarationParams = Omit<
  Query<"v1_independence_declarations_list">,
  "page" | "page_size"
>;

const BASE = "/api/v1";

type SaveVars<T> = { id?: undefined; data: T } | { id: string; data: Partial<T> };

function save<T, R>(resource: string, vars: SaveVars<T>): Promise<R> {
  return vars.id === undefined
    ? apiFetch<R>(`${BASE}/${resource}/`, { method: "POST", json: vars.data })
    : apiFetch<R>(`${BASE}/${resource}/${vars.id}/`, { method: "PATCH", json: vars.data });
}

function post<R>(path: string, json?: unknown): Promise<R> {
  return apiFetch<R>(`${BASE}/${path}`, { method: "POST", json });
}

function remove(resource: string, id: string): Promise<void> {
  return apiFetch<undefined>(`${BASE}/${resource}/${id}/`, { method: "DELETE" });
}

function invalidate(client: QueryClient, ...keys: QueryKey[]): Promise<unknown> {
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

/**
 * Règle d'invalidation : toute mutation d'un objet de mission invalide le détail (statut, phase
 * et droits peuvent changer), les étapes, la fiche de suivi et la liste des missions.
 */
function invalidateMission(client: QueryClient, missionId: string, ...extra: QueryKey[]) {
  return invalidate(
    client,
    missionKeys.detail(missionId),
    missionKeys.steps(missionId),
    missionKeys.tracking(missionId),
    missionKeys.lists(),
    ...extra,
  );
}

// ---- Missions ------------------------------------------------------------------------------

function filtersOf(params: object): string {
  const filters: Record<string, unknown> = { ...params };
  for (const key of ["page", "page_size", "ordering"]) delete filters[key];
  return JSON.stringify(filters);
}

function sameFilters(previousKey: QueryKey, params: MissionParams): boolean {
  return filtersOf(previousKey[2] as object) === filtersOf(params);
}

export function useMissions(params: MissionParams = {}) {
  return useQuery({
    queryKey: missionKeys.list(params),
    queryFn: () => apiFetch<S["PaginatedMissionListeList"]>(`${BASE}/missions/${toQuery(params)}`),
    // Garde la page précédente seulement si les filtres sont identiques (pagination, tri).
    placeholderData: (previous, previousQuery) =>
      previousQuery !== undefined && sameFilters(previousQuery.queryKey, params)
        ? previous
        : undefined,
  });
}

export function useMission(id: string | undefined) {
  return useQuery({
    queryKey: missionKeys.detail(id),
    queryFn: () => apiFetch<Mission>(`${BASE}/missions/${id}/`),
    enabled: id !== undefined,
  });
}

export function useSaveMission() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<MissionInput>) => save<MissionInput, Mission>("missions", vars),
    onSuccess: (mission) => invalidateMission(client, mission.id),
  });
}

export function useDeleteMission() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => remove("missions", id),
    onSuccess: (_, id) => {
      // La mission n'existe plus : la retirer du cache évite un refetch en 404 (flash « introuvable »).
      for (const queryKey of [
        missionKeys.detail(id),
        missionKeys.steps(id),
        missionKeys.tracking(id),
        missionKeys.assignments(id),
      ]) {
        client.removeQueries({ queryKey });
      }
      return invalidate(client, missionKeys.lists());
    },
  });
}

export type MissionAction = "plan" | "launch" | "issue-order" | "suspend" | "resume" | "cancel";

export function useMissionTransition() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: string; action: MissionAction; body?: object }) =>
      post<Mission>(`missions/${id}/${action}/`, body),
    onSuccess: (mission) =>
      invalidateMission(client, mission.id, missionKeys.assignments(mission.id)),
  });
}

export function useDefaultAuditees(id: string | undefined) {
  return useQuery({
    queryKey: missionKeys.defaultAuditees(id),
    queryFn: () => apiFetch<UtilisateurResume[]>(`${BASE}/missions/${id}/default-auditees/`),
    enabled: id !== undefined,
  });
}

/** Tous les utilisateurs (sans pagination visible) ; le filtrage se fait localement. */
export function useAllUsers(params: Omit<UserParams, "page" | "page_size"> = {}) {
  return useQuery({
    queryKey: missionKeys.users(params),
    queryFn: () => fetchAllPages<UtilisateurResume>("users", params),
  });
}

// ---- Équipe et déclarations ----------------------------------------------------------------

export function useAssignments(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.assignments(missionId),
    queryFn: () => fetchAllPages<Affectation>("mission-assignments", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useAssign() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: AffectationInput) => post<Affectation>("mission-assignments/", data),
    onSuccess: (a) =>
      invalidateMission(
        client,
        a.mission,
        missionKeys.assignments(a.mission),
        missionKeys.declarations(),
      ),
  });
}

export function useUnassign() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) => remove("mission-assignments", id),
    onSuccess: (_, { missionId }) =>
      invalidateMission(
        client,
        missionId,
        missionKeys.assignments(missionId),
        missionKeys.declarations(),
      ),
  });
}

export function useReplaceChief() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, utilisateur }: { id: string; utilisateur: number }) =>
      post<Mission>(`missions/${id}/replace-chief/`, { utilisateur }),
    onSuccess: (m) =>
      invalidateMission(client, m.id, missionKeys.assignments(m.id), missionKeys.declarations()),
  });
}

export function useDeclarations(params: DeclarationParams = {}) {
  return useQuery({
    queryKey: missionKeys.declarations(params),
    queryFn: () =>
      fetchAllPages<Declaration>("independence-declarations", {
        ...params,
        mine: params.mine === undefined ? undefined : String(params.mine),
      }),
  });
}

export function useConfirmDeclaration() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      conflit = false,
      description_conflit,
    }: {
      id: string;
      conflit?: boolean;
      description_conflit?: string;
    }) =>
      post<Declaration>(`independence-declarations/${id}/confirm/`, {
        confirme: true,
        conflit,
        ...(description_conflit !== undefined ? { description_conflit } : {}),
      }),
    onSuccess: (d) =>
      invalidateMission(
        client,
        d.mission,
        missionKeys.assignments(d.mission),
        missionKeys.declarations(),
      ),
  });
}

export function useArbitrateDeclaration() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, justification }: { id: string; justification: string }) =>
      post<Declaration>(`independence-declarations/${id}/arbitrate/`, { justification }),
    onSuccess: (d) =>
      invalidateMission(
        client,
        d.mission,
        missionKeys.assignments(d.mission),
        missionKeys.declarations(),
      ),
  });
}

// ---- Étapes --------------------------------------------------------------------------------

export function useSteps(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.steps(missionId),
    queryFn: () => apiFetch<Etape[]>(`${BASE}/mission-steps/${toQuery({ mission: missionId })}`),
    enabled: missionId !== undefined,
  });
}

export function useStep(id: string | undefined) {
  return useQuery({
    queryKey: missionKeys.step(id),
    queryFn: () => apiFetch<Etape>(`${BASE}/mission-steps/${id}/`),
    enabled: id !== undefined,
  });
}

export type StepAction =
  "start" | "complete" | "validate" | "return" | "reopen" | "not-applicable" | "restore";

export function useStepAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, motif }: { id: string; action: StepAction; motif?: string }) =>
      post<Etape>(`mission-steps/${id}/${action}/`, motif !== undefined ? { motif } : undefined),
    onSuccess: (step) => invalidateMission(client, step.mission, missionKeys.step(step.id)),
  });
}

export function useUpdateStepPlanning() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EtapeInput }) =>
      save<EtapeInput, Etape>("mission-steps", { id, data }),
    onSuccess: (step) => invalidateMission(client, step.mission, missionKeys.step(step.id)),
  });
}

export function useTracking(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.tracking(missionId),
    queryFn: () => apiFetch<FicheSuivi>(`${BASE}/missions/${missionId}/tracking/`),
    enabled: missionId !== undefined,
  });
}

// ---- Réunions ------------------------------------------------------------------------------

export function useMeetings(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.meetings(missionId),
    queryFn: () => fetchAllPages<Reunion>("meetings", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveMeeting() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<ReunionInput>) => save<ReunionInput, Reunion>("meetings", vars),
    onSuccess: (r) => invalidateMission(client, r.mission, missionKeys.meetings(r.mission)),
  });
}

export function useDeleteMeeting() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) => remove("meetings", id),
    onSuccess: (_, { missionId }) =>
      invalidateMission(client, missionId, missionKeys.meetings(missionId)),
  });
}

export function useMarkMeetingHeld() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => post<Reunion>(`meetings/${id}/mark-held/`),
    onSuccess: (r) => invalidateMission(client, r.mission, missionKeys.meetings(r.mission)),
  });
}

// ---- Entretiens ----------------------------------------------------------------------------

export function useInterviews(params: InterviewParams = {}) {
  return useQuery({
    queryKey: missionKeys.interviews(params),
    queryFn: () => fetchAllPages<Entretien>("interviews", params),
  });
}

export function useSaveInterview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<EntretienInput>) =>
      save<EntretienInput, Entretien>("interviews", vars),
    onSuccess: (e) => invalidateMission(client, e.mission, missionKeys.interviews()),
  });
}

export function useDeleteInterview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) => remove("interviews", id),
    onSuccess: (_, { missionId }) => invalidateMission(client, missionId, missionKeys.interviews()),
  });
}

export function useInterviewAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      motif,
    }: {
      id: string;
      action: "mark-done" | "cancel";
      motif?: string;
    }) =>
      post<Entretien>(`interviews/${id}/${action}/`, motif !== undefined ? { motif } : undefined),
    onSuccess: (e) => invalidateMission(client, e.mission, missionKeys.interviews()),
  });
}

// ---- Risques de la mission -----------------------------------------------------------------

export function useMissionRisks(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.risks(missionId),
    queryFn: () => fetchAllPages<RisqueMission>("mission-risks", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveMissionRisk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<RisqueMissionInput>) =>
      save<RisqueMissionInput, RisqueMission>("mission-risks", vars),
    onSuccess: (r) =>
      invalidateMission(
        client,
        r.mission,
        missionKeys.risks(r.mission),
        missionKeys.matrix(r.mission),
        missionKeys.proposedRisks(),
      ),
  });
}

export function useDeleteMissionRisk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) => remove("mission-risks", id),
    onSuccess: (_, { missionId }) =>
      invalidateMission(
        client,
        missionId,
        missionKeys.risks(missionId),
        missionKeys.matrix(missionId),
        missionKeys.proposedRisks(),
      ),
  });
}

export function useMissionMatrix(missionId: string | undefined) {
  return useQuery({
    queryKey: missionKeys.matrix(missionId),
    queryFn: () => apiFetch<MatriceMission>(`${BASE}/missions/${missionId}/risk-matrix/`),
    enabled: missionId !== undefined,
  });
}

/** Risques ajoutés par les missions, en attente d'intégration à la cartographie (lecture RAI). */
export function useProposedRisks() {
  return useQuery({
    queryKey: missionKeys.proposedRisks(),
    queryFn: () => fetchAllPages<RisqueMission>("mission-risks", { nouveau: "true" }),
  });
}
