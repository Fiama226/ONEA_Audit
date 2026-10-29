import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiFetch } from "@/api/client";
import { missionKeys } from "../missions/keys";
import type {
  AvisInput,
  DescriptionProcessus,
  DescriptionProcessusInput,
  ForceFaiblesse,
  ForceFaiblesseInput,
  GrilleSeparation,
  GrilleSeparationInput,
  InstantaneReferentiel,
  LigneMarc,
  LigneMarcInput,
  ObjectifAudit,
  ObjectifAuditInput,
  Question,
  QuestionInput,
  Questionnaire,
  QuestionnaireInput,
  RapportOrientation,
  RapportOrientationInput,
  ReferentielAudit,
  TypeQuestionnaire,
} from "./types";

const BASE = "/api/v1";

/** Clés TanStack Query de l'analyse ; `mission(id)` est le préfixe de toutes les clés d'une mission. */
export const analyseKeys = {
  all: ["analyse"] as QueryKey,
  mission: (missionId: string | undefined) => ["analyse", missionId] as QueryKey,
  framework: (missionId: string | undefined) => ["analyse", missionId, "framework"] as QueryKey,
  snapshot: (missionId: string | undefined) => ["analyse", missionId, "snapshot"] as QueryKey,
  questionnaires: (missionId: string | undefined, type?: TypeQuestionnaire) =>
    ["analyse", missionId, "questionnaires", type ?? null] as QueryKey,
  questions: (questionnaireId: string | undefined) =>
    ["analyse", "questions", questionnaireId] as QueryKey,
  processDescriptions: (missionId: string | undefined) =>
    ["analyse", missionId, "process-descriptions"] as QueryKey,
  segregationGrids: (missionId: string | undefined) =>
    ["analyse", missionId, "segregation-grids"] as QueryKey,
  marcLines: (missionId: string | undefined) => ["analyse", missionId, "marc-lines"] as QueryKey,
  strengthsWeaknesses: (missionId: string | undefined) =>
    ["analyse", missionId, "strengths-weaknesses"] as QueryKey,
  objectives: (missionId: string | undefined) => ["analyse", missionId, "objectives"] as QueryKey,
  orientation: (missionId: string | undefined) => ["analyse", missionId, "orientation"] as QueryKey,
};

type SaveVars<T> = { id?: undefined; data: T } | { id: string; data: Partial<T> };

function save<T, R>(resource: string, vars: SaveVars<T>): Promise<R> {
  return vars.id === undefined
    ? apiFetch<R>(`${BASE}/${resource}/`, { method: "POST", json: vars.data })
    : apiFetch<R>(`${BASE}/${resource}/${vars.id}/`, { method: "PATCH", json: vars.data });
}

function remove(resource: string, id: string): Promise<void> {
  return apiFetch<undefined>(`${BASE}/${resource}/${id}/`, { method: "DELETE" });
}

/**
 * Toute mutation de l'analyse invalide les clés de la mission, ses étapes (les livrables manquants
 * changent), l'étape courante et le détail (droits, étape courante).
 */
function invalidateAnalyse(client: QueryClient, missionId: string, ...extra: QueryKey[]) {
  const keys: QueryKey[] = [
    analyseKeys.mission(missionId),
    missionKeys.steps(missionId),
    [...missionKeys.all, "step"],
    missionKeys.detail(missionId),
    ...extra,
  ];
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

type Deleting = { id: string; missionId: string };

// ---- Référentiel d'audit -------------------------------------------------------------------

export function useAuditFramework(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.framework(missionId),
    queryFn: () => apiFetch<ReferentielAudit>(`${BASE}/audit-frameworks/${missionId}/`),
    enabled: missionId !== undefined,
  });
}

export function useFrameworkSnapshot(missionId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: analyseKeys.snapshot(missionId),
    queryFn: () =>
      apiFetch<InstantaneReferentiel>(`${BASE}/audit-frameworks/${missionId}/snapshot/`),
    enabled: enabled && missionId !== undefined,
  });
}

export function useGiveOpinion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, ...data }: AvisInput & { missionId: string }) =>
      apiFetch<unknown>(`${BASE}/audit-frameworks/${missionId}/opinions/`, {
        method: "POST",
        json: data,
      }),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

// ---- Questionnaires ------------------------------------------------------------------------

export function useQuestionnaires(missionId: string | undefined, type?: TypeQuestionnaire) {
  return useQuery({
    queryKey: analyseKeys.questionnaires(missionId, type),
    queryFn: () =>
      fetchAllPages<Questionnaire>("analysis-questionnaires", { mission: missionId, type }),
    enabled: missionId !== undefined,
  });
}

export function useQuestions(questionnaireId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.questions(questionnaireId),
    queryFn: () =>
      fetchAllPages<Question>("analysis-questions", { questionnaire: questionnaireId }),
    enabled: questionnaireId !== undefined,
  });
}

export function useSaveQuestionnaire() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<QuestionnaireInput>) =>
      save<QuestionnaireInput, Questionnaire>("analysis-questionnaires", vars),
    onSuccess: (q) => invalidateAnalyse(client, q.mission),
  });
}

export function useDeleteQuestionnaire() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("analysis-questionnaires", id),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

export function useSaveQuestion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<QuestionInput> & { missionId: string }) =>
      save<QuestionInput, Question>(
        "analysis-questions",
        vars.id === undefined ? { data: vars.data } : { id: vars.id, data: vars.data },
      ),
    onSuccess: (q, { missionId }) =>
      invalidateAnalyse(client, missionId, analyseKeys.questions(q.questionnaire)),
  });
}

export function useDeleteQuestion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting & { questionnaireId?: string }) =>
      remove("analysis-questions", id),
    onSuccess: (_, { id, missionId, questionnaireId }) => {
      // Pas de requête par question : on retire l'élément supprimé de la liste en cache
      // pour ne jamais l'afficher ni le recharger.
      client.setQueryData<{ results: Question[]; count: number }>(
        analyseKeys.questions(questionnaireId),
        (old) =>
          old && {
            count: old.count - 1,
            results: old.results.filter((q) => q.id !== id),
          },
      );
      return invalidateAnalyse(client, missionId, analyseKeys.questions(questionnaireId));
    },
  });
}

// ---- Description des processus -------------------------------------------------------------

export function useProcessDescriptions(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.processDescriptions(missionId),
    queryFn: () =>
      fetchAllPages<DescriptionProcessus>("process-descriptions", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveProcessDescription() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<DescriptionProcessusInput>) =>
      save<DescriptionProcessusInput, DescriptionProcessus>("process-descriptions", vars),
    onSuccess: (d) => invalidateAnalyse(client, d.mission),
  });
}

export function useDeleteProcessDescription() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("process-descriptions", id),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

// ---- Séparation des tâches -----------------------------------------------------------------

export function useSegregationGrids(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.segregationGrids(missionId),
    queryFn: () => fetchAllPages<GrilleSeparation>("segregation-grids", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveSegregationGrid() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<GrilleSeparationInput>) =>
      save<GrilleSeparationInput, GrilleSeparation>("segregation-grids", vars),
    onSuccess: (g) => invalidateAnalyse(client, g.mission),
  });
}

export function useDeleteSegregationGrid() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("segregation-grids", id),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

// ---- MARC ----------------------------------------------------------------------------------

export function useMarcLines(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.marcLines(missionId),
    queryFn: () => fetchAllPages<LigneMarc>("marc-lines", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveMarcLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<LigneMarcInput>) =>
      save<LigneMarcInput, LigneMarc>("marc-lines", vars),
    onSuccess: (l) => invalidateAnalyse(client, l.mission),
  });
}

export function useDeleteMarcLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("marc-lines", id),
    onSuccess: (_, { id, missionId }) => {
      client.removeQueries({ queryKey: [...analyseKeys.marcLines(missionId), id] });
      return invalidateAnalyse(client, missionId);
    },
  });
}

export function useInitializeMarc() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId }: { missionId: string }) =>
      apiFetch<LigneMarc[]>(`${BASE}/marc-lines/initialize/`, {
        method: "POST",
        json: { mission: missionId },
      }),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

// ---- Forces et faiblesses ------------------------------------------------------------------

export function useStrengthsWeaknesses(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.strengthsWeaknesses(missionId),
    queryFn: () => fetchAllPages<ForceFaiblesse>("strengths-weaknesses", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveStrengthWeakness() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveVars<ForceFaiblesseInput>) =>
      save<ForceFaiblesseInput, ForceFaiblesse>("strengths-weaknesses", vars),
    onSuccess: (f) => invalidateAnalyse(client, f.mission),
  });
}

export function useDeleteStrengthWeakness() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("strengths-weaknesses", id),
    onSuccess: (_, { id, missionId }) => {
      client.removeQueries({ queryKey: [...analyseKeys.strengthsWeaknesses(missionId), id] });
      return invalidateAnalyse(client, missionId);
    },
  });
}

// ---- Objectifs d'audit ---------------------------------------------------------------------

export function useAuditObjectives(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.objectives(missionId),
    queryFn: () => fetchAllPages<ObjectifAudit>("audit-objectives", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveAuditObjective() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ObjectifAuditInput> }) =>
      save<ObjectifAuditInput, ObjectifAudit>("audit-objectives", { id, data }),
    onSuccess: (o) => invalidateAnalyse(client, o.mission),
  });
}

export function useDeleteAuditObjective() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: Deleting) => remove("audit-objectives", id),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

export function useInitializeObjectives() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId }: { missionId: string }) =>
      apiFetch<ObjectifAudit[]>(`${BASE}/audit-objectives/initialize/`, {
        method: "POST",
        json: { mission: missionId },
      }),
    onSuccess: (_, { missionId }) => invalidateAnalyse(client, missionId),
  });
}

// ---- Rapport d'orientation -----------------------------------------------------------------

export function useOrientationReport(missionId: string | undefined) {
  return useQuery({
    queryKey: analyseKeys.orientation(missionId),
    queryFn: () => apiFetch<RapportOrientation>(`${BASE}/orientation-reports/${missionId}/`),
    enabled: missionId !== undefined,
  });
}

export function useSaveOrientationReport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, data }: { missionId: string; data: RapportOrientationInput }) =>
      apiFetch<RapportOrientation>(`${BASE}/orientation-reports/${missionId}/`, {
        method: "PATCH",
        json: data,
      }),
    onSuccess: (r) => invalidateAnalyse(client, r.mission),
  });
}
