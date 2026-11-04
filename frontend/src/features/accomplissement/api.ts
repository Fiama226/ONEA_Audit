import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { apiFetch } from "@/api/client";
import { toQuery, type QueryParams } from "@/api/query";
import { uploadWithProgress } from "@/api/upload";
import { missionKeys } from "../missions/keys";
import { accomplissementKeys } from "./keys";
import type {
  Fiche,
  FicheAction,
  FicheDetail,
  FicheInput,
  InstantaneProgramme,
  Piece,
  PieceUpdate,
  ProgrammeTravail,
  ProgrammeTravailInput,
  SyntheseProgramme,
  TestPrevu,
  TestPrevuInput,
} from "./types";

const BASE = "/api/v1";

/**
 * Toute mutation invalide les clés de l'accomplissement de la mission, ses étapes (les livrables
 * changent), l'étape courante, le détail et le suivi du lot 3 (statuts, droits).
 */
export function invalidateAccomplissement(
  client: QueryClient,
  missionId: string,
  ...extra: QueryKey[]
) {
  const keys: QueryKey[] = [
    accomplissementKeys.mission(missionId),
    missionKeys.steps(missionId),
    [...missionKeys.all, "step"],
    missionKeys.detail(missionId),
    missionKeys.tracking(missionId),
    ...extra,
  ];
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

// ---- Programmes de travail --------------------------------------------------------------------

export function useWorkPrograms(missionId: string | undefined) {
  return useQuery({
    queryKey: accomplissementKeys.programs(missionId),
    queryFn: () => fetchAllPages<ProgrammeTravail>("work-programs", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

export function useSaveWorkProgram() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { missionId: string; data: ProgrammeTravailInput }) =>
      apiFetch<ProgrammeTravail>(`${BASE}/work-programs/`, { method: "POST", json: data }),
    onSuccess: (_result, { missionId }) => invalidateAccomplissement(client, missionId),
  });
}

export function useDeleteWorkProgram() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/work-programs/${id}/`, { method: "DELETE" }),
    onSuccess: async (_result, { id, missionId }) => {
      client.removeQueries({ queryKey: [...accomplissementKeys.programs(missionId), id] });
      await invalidateAccomplissement(client, missionId);
    },
  });
}

export function useProgramSummary(missionId: string | undefined) {
  return useQuery({
    queryKey: accomplissementKeys.summary(missionId),
    queryFn: () =>
      apiFetch<SyntheseProgramme>(
        `${BASE}/work-programs/summary/${toQuery({ mission: missionId })}`,
      ),
    enabled: missionId !== undefined,
  });
}

/** Versions validées du programme : la liste n'est pas paginée, l'API renvoie un tableau nu. */
export function useSnapshots(missionId: string | undefined) {
  return useQuery({
    queryKey: accomplissementKeys.snapshots(missionId),
    queryFn: () =>
      apiFetch<InstantaneProgramme[]>(
        `${BASE}/work-programs/snapshots/${toQuery({ mission: missionId })}`,
      ),
    enabled: missionId !== undefined,
  });
}

// ---- Tests prévus -----------------------------------------------------------------------------

export function usePlannedTests(params: { mission: string | undefined } & QueryParams) {
  return useQuery({
    queryKey: accomplissementKeys.tests(params.mission, params),
    queryFn: () => fetchAllPages<TestPrevu>("planned-tests", params),
    enabled: params.mission !== undefined,
    placeholderData: keepPreviousData,
  });
}

type SaveTest = { missionId: string } & (
  { id?: undefined; data: TestPrevuInput } | { id: string; data: Partial<TestPrevuInput> }
);

export function useSavePlannedTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveTest) =>
      vars.id === undefined
        ? apiFetch<TestPrevu>(`${BASE}/planned-tests/`, { method: "POST", json: vars.data })
        : apiFetch<TestPrevu>(`${BASE}/planned-tests/${vars.id}/`, {
            method: "PATCH",
            json: vars.data,
          }),
    onSuccess: (_result, { missionId }) => invalidateAccomplissement(client, missionId),
  });
}

export function useDeletePlannedTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/planned-tests/${id}/`, { method: "DELETE" }),
    onSuccess: (_result, { missionId }) => invalidateAccomplissement(client, missionId),
  });
}

export function useAbandonTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, motif }: { id: string; missionId: string; motif: string }) =>
      apiFetch<TestPrevu>(`${BASE}/planned-tests/${id}/abandon/`, {
        method: "POST",
        json: { motif },
      }),
    onSuccess: (_result, { missionId }) => invalidateAccomplissement(client, missionId),
  });
}

// ---- Fiches de test ---------------------------------------------------------------------------

export function useTestSheets(params: { mission: string | undefined } & QueryParams) {
  return useQuery({
    queryKey: accomplissementKeys.sheets(params.mission, params),
    queryFn: () => fetchAllPages<Fiche>("test-sheets", params),
    enabled: params.mission !== undefined,
    placeholderData: keepPreviousData,
  });
}

export function useTestSheet(id: string | undefined) {
  return useQuery({
    queryKey: accomplissementKeys.sheet(id),
    queryFn: () => apiFetch<FicheDetail>(`${BASE}/test-sheets/${id}/`),
    enabled: id !== undefined,
  });
}

type SaveSheet = { missionId: string } & (
  { id?: undefined; data: FicheInput } | { id: string; data: Partial<FicheInput> }
);

export function useSaveTestSheet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (vars: SaveSheet) =>
      vars.id === undefined
        ? apiFetch<FicheDetail>(`${BASE}/test-sheets/`, { method: "POST", json: vars.data })
        : apiFetch<FicheDetail>(`${BASE}/test-sheets/${vars.id}/`, {
            method: "PATCH",
            json: vars.data,
          }),
    onSuccess: (_result, vars) =>
      invalidateAccomplissement(
        client,
        vars.missionId,
        ...(vars.id === undefined ? [] : [accomplissementKeys.sheet(vars.id)]),
      ),
  });
}

/** Transition d'une fiche ; « return » exige un motif. */
export function useSheetAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      motif,
    }: {
      id: string;
      missionId: string;
      action: FicheAction;
      motif?: string;
    }) =>
      apiFetch<FicheDetail>(`${BASE}/test-sheets/${id}/${action}/`, {
        method: "POST",
        json: motif === undefined ? {} : { motif },
      }),
    onSuccess: (_result, { id, missionId }) =>
      invalidateAccomplissement(client, missionId, accomplissementKeys.sheet(id)),
  });
}

// ---- Pièces justificatives --------------------------------------------------------------------

export function useEvidence(ficheId: string | undefined) {
  return useQuery({
    queryKey: accomplissementKeys.evidence(ficheId),
    queryFn: () => fetchAllPages<Piece>("evidence", { fiche: ficheId }),
    enabled: ficheId !== undefined,
  });
}

export type UploadVars = {
  ficheId: string;
  missionId: string;
  file: File;
  libelle: string;
  description?: string;
  onProgress: (ratio: number) => void;
  signal?: AbortSignal;
};

/** Dépôt d'une pièce avec progression ; l'empreinte SHA-256 est calculée et conservée par le serveur. */
export function useUploadEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ ficheId, file, libelle, description, onProgress, signal }: UploadVars) => {
      const form = new FormData();
      form.append("fichier", file);
      form.append("libelle", libelle);
      form.append("description", description ?? "");
      return uploadWithProgress<Piece>(
        `${BASE}/evidence/${toQuery({ fiche: ficheId })}`,
        form,
        onProgress,
        signal,
      );
    },
    onSuccess: (_result, { ficheId, missionId }) =>
      invalidateAccomplissement(
        client,
        missionId,
        accomplissementKeys.evidence(ficheId),
        accomplissementKeys.sheet(ficheId),
      ),
  });
}

export function useUpdateEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      ficheId: string;
      missionId: string;
      data: PieceUpdate;
    }) => apiFetch<Piece>(`${BASE}/evidence/${id}/`, { method: "PATCH", json: data }),
    onSuccess: (_result, { ficheId, missionId }) =>
      invalidateAccomplissement(
        client,
        missionId,
        accomplissementKeys.evidence(ficheId),
        accomplissementKeys.sheet(ficheId),
      ),
  });
}

export function useRemoveEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; ficheId: string; missionId: string }) =>
      apiFetch<undefined>(`${BASE}/evidence/${id}/`, { method: "DELETE" }),
    onSuccess: async (_result, { ficheId, missionId }) => {
      await invalidateAccomplissement(
        client,
        missionId,
        accomplissementKeys.evidence(ficheId),
        accomplissementKeys.sheet(ficheId),
      );
    },
  });
}
