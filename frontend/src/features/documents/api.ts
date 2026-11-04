import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { fetchAllPages } from "@/api/allPages";
import { apiDownload, apiFetch, apiUpload } from "@/api/client";
import { ApiError } from "@/api/errors";
import { toQuery } from "@/api/query";
import type { components, operations } from "@/api/schema";
import { downloadBlob } from "@/lib/download";
import { documentKeys } from "./keys";
import { isInProgress } from "./labels";
import type {
  ApercuFormat,
  ApercuNumero,
  Consultation,
  Document,
  DocumentDisponible,
  DocumentListe,
  DocumentType,
  DocumentVersion,
  FormatFichier,
  FormatNumerotation,
  FormatNumerotationInput,
  Gabarit,
} from "./types";

export { documentKeys };

type S = components["schemas"];
type Query<K extends keyof operations> = NonNullable<operations[K]["parameters"]["query"]>;
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type TemplateParams = Query<"v1_templates_list">;
export type DocumentParams = Query<"v1_documents_list">;

const BASE = "/api/v1";

/** Durée maximale d'interrogation d'une génération en cours. */
export const POLL_INTERVAL_MS = 2_000;
export const POLL_TIMEOUT_MS = 3 * 60 * 1000;
export const GENERATION_TIMEOUT_MESSAGE =
  "La génération prend plus de temps que prévu : revenez plus tard.";

function invalidate(client: QueryClient, ...keys: QueryKey[]): Promise<unknown> {
  return Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

export function useDocumentTypes(enabled = true) {
  return useQuery({
    queryKey: documentKeys.types(),
    queryFn: () => apiFetch<DocumentType[]>(`${BASE}/document-types/`),
    enabled,
  });
}

export function useTemplates(params: TemplateParams = {}) {
  return useQuery({
    queryKey: documentKeys.templateList(params),
    queryFn: () => apiFetch<Page<Gabarit>>(`${BASE}/templates/${toQuery(params)}`),
  });
}

/** Toutes les versions de gabarit d'un type (toutes les pages). */
export function useTemplateVersions(typeDocument: string) {
  return useQuery({
    queryKey: documentKeys.templateList({ type_document: typeDocument, all: true }),
    queryFn: () =>
      fetchAllPages<Gabarit>("templates", { type_document: typeDocument, ordering: "-version" }),
  });
}

export function useTemplate(id: string | undefined) {
  return useQuery({
    queryKey: documentKeys.template(id),
    queryFn: () => apiFetch<Gabarit>(`${BASE}/templates/${id}/`),
    enabled: id !== undefined,
  });
}

export type UploadTemplateInput = {
  type_document: string;
  fichier: File;
  commentaire?: string;
  /** Annule l'envoi en cours (fermeture de la boîte de dépôt). */
  signal?: AbortSignal;
};

export function useUploadTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: UploadTemplateInput) => {
      const body = new FormData();
      body.append("type_document", input.type_document);
      body.append("fichier", input.fichier);
      body.append("commentaire", input.commentaire ?? "");
      return apiUpload<Gabarit>(`${BASE}/templates/`, body, input.signal);
    },
    // onSettled : un envoi annulé a pu aboutir côté serveur, les listes sont relues dans tous les cas.
    onSettled: () => invalidate(client, documentKeys.templates(), documentKeys.types()),
  });
}

export function useActivateTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Gabarit>(`${BASE}/templates/${id}/activate/`, { method: "POST" }),
    onSuccess: () => invalidate(client, documentKeys.templates(), documentKeys.types()),
  });
}

export function useNumberingFormats() {
  return useQuery({
    queryKey: documentKeys.numbering(),
    queryFn: () => apiFetch<FormatNumerotation[]>(`${BASE}/numbering-formats/`),
  });
}

export function useUpdateNumberingFormat() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ typeDocument, data }: { typeDocument: string; data: FormatNumerotationInput }) =>
      apiFetch<FormatNumerotation>(`${BASE}/numbering-formats/${typeDocument}/`, {
        method: "PATCH",
        json: data,
      }),
    onSuccess: () => invalidate(client, documentKeys.numbering(), documentKeys.types()),
  });
}

export function useNumberingPreview() {
  return useMutation({
    mutationFn: ({ signal, ...data }: ApercuFormat & { signal?: AbortSignal }) =>
      apiFetch<ApercuNumero>(`${BASE}/numbering-formats/preview/`, {
        method: "POST",
        json: data,
        signal,
      }),
  });
}

export function useDocuments(params: DocumentParams = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => apiFetch<Page<DocumentListe>>(`${BASE}/documents/${toQuery(params)}`),
  });
}

export function useDocument(id: string | undefined) {
  return useQuery({
    queryKey: documentKeys.document(id),
    queryFn: () => apiFetch<Document>(`${BASE}/documents/${id}/`),
    enabled: id !== undefined,
  });
}

/**
 * Budget d'interrogation : `signature` identifie le traitement en cours ("" = aucun). Après
 * 3 minutes, `timedOut` passe à vrai et `stoppedRef.current` coupe l'interrogation ; un changement de
 * signature (nouvelle génération, nouvel état) ou la fin du traitement remet le compteur à zéro.
 */
function usePollBudget(signature: string, stoppedRef: RefObject<boolean>) {
  const [expired, setExpired] = useState<string | null>(null);
  // `epoch` change à chaque relance manuelle : nouveau budget de 3 minutes pour la même signature.
  const [epoch, setEpoch] = useState(0);
  const key = signature === "" ? "" : `${signature}#${epoch}`;
  const timedOut = key !== "" && expired === key;
  useEffect(() => {
    stoppedRef.current = timedOut;
  }, [timedOut, stoppedRef]);
  useEffect(() => {
    if (key === "") return;
    const timer = setTimeout(() => setExpired(key), POLL_TIMEOUT_MS);
    return () => {
      clearTimeout(timer);
      setExpired(null);
    };
  }, [key]);
  return { timedOut, restart: useCallback(() => setEpoch((n) => n + 1), []) };
}

function timeoutError(timedOut: boolean): ApiError | null {
  return timedOut ? new ApiError(0, GENERATION_TIMEOUT_MESSAGE) : null;
}

function pendingSignature(items: DocumentDisponible[] | undefined): string {
  return (items ?? [])
    .flatMap((d) => {
      const v = d.document?.derniere_version;
      if (v && isInProgress(v)) return [`${v.id}:${v.statut}:${v.statut_pdf}`];
      return d.en_cours ? [`${d.type_document}:${d.objet_id}`] : [];
    })
    .sort()
    .join("|");
}

/**
 * Une relecture est « d'arrière-plan » quand elle poursuit l'interrogation d'un traitement déjà
 * affiché comme en cours ; le premier chargement et la relance manuelle viennent de l'agent
 * (`user` : relance manuelle en attente).
 */
const isBackgroundPoll = (inProgress: boolean, user: boolean): boolean => inProgress && !user;

/** Relance manuelle en attente : `mark()` la signale, `take()` la lit puis l'efface. */
function useManualRefetch(): { mark: () => void; take: () => boolean } {
  const flagRef = useRef(false);
  const [api] = useState(() => ({
    mark: () => {
      flagRef.current = true;
    },
    take: () => {
      const value = flagRef.current;
      flagRef.current = false;
      return value;
    },
  }));
  return api;
}

export function useAvailableDocuments(missionId: string | undefined) {
  const stoppedRef = useRef(false);
  const manualRefetch = useManualRefetch();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: documentKeys.available(missionId),
    queryFn: () => {
      const manual = manualRefetch.take();
      const previous = client.getQueryData<DocumentDisponible[]>(documentKeys.available(missionId));
      return apiFetch<DocumentDisponible[]>(
        `${BASE}/documents/available/${toQuery({ mission: missionId })}`,
        { background: isBackgroundPoll(pendingSignature(previous) !== "", manual) },
      );
    },
    enabled: missionId !== undefined,
    // Génération Word ou PDF en cours : le statut est relu toutes les 2 s, pendant 3 minutes au plus.
    refetchInterval: (q) =>
      pendingSignature(q.state.data) !== "" && !stoppedRef.current ? POLL_INTERVAL_MS : false,
  });
  const { timedOut, restart } = usePollBudget(pendingSignature(query.data), stoppedRef);
  const { refetch } = query;
  const restartPolling = useCallback(() => {
    restart();
    manualRefetch.mark();
    void refetch();
  }, [restart, refetch, manualRefetch]);
  return Object.assign(query, {
    timeoutError: timeoutError(timedOut),
    /** Relance l'interrogation pour un nouveau budget de 3 minutes. */
    restartPolling,
  });
}

/** Toute mutation de génération rafraîchit les documents disponibles, les listes et le détail. */
function invalidateGeneration(client: QueryClient, version: DocumentVersion) {
  return invalidate(
    client,
    documentKeys.availables(),
    documentKeys.lists(),
    documentKeys.document(version.document),
    documentKeys.version(version.id),
  );
}

export function useGenerateDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: S["GenerationRequest"]) =>
      apiFetch<DocumentVersion>(`${BASE}/documents/generate/`, { method: "POST", json: input }),
    onSuccess: (version) => invalidateGeneration(client, version),
  });
}

/**
 * Version d'un document. Tant que la génération ou le PDF est en cours, interroge toutes les 2 s ;
 * abandonne après 3 minutes (`timeoutError` renseigné).
 */
export function useVersion(id: string | undefined) {
  const stoppedRef = useRef(false);
  const manualRefetch = useManualRefetch();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: documentKeys.version(id),
    queryFn: () => {
      const manual = manualRefetch.take();
      const previous = client.getQueryData<DocumentVersion>(documentKeys.version(id));
      return apiFetch<DocumentVersion>(`${BASE}/document-versions/${id}/`, {
        background: isBackgroundPoll(previous !== undefined && isInProgress(previous), manual),
      });
    },
    enabled: id !== undefined,
    refetchInterval: (q) => {
      const data = q.state.data;
      return data && isInProgress(data) && !stoppedRef.current ? POLL_INTERVAL_MS : false;
    },
  });
  const data = query.data;
  const signature =
    data && isInProgress(data) ? `${data.id}:${data.statut}:${data.statut_pdf}` : "";
  const { timedOut, restart } = usePollBudget(signature, stoppedRef);
  const { refetch } = query;
  const restartPolling = useCallback(() => {
    restart();
    manualRefetch.mark();
    void refetch();
  }, [restart, refetch, manualRefetch]);
  return Object.assign(query, {
    timeoutError: timeoutError(timedOut),
    /** Relance l'interrogation pour un nouveau budget de 3 minutes. */
    restartPolling,
  });
}

export function useRetryPdf() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      apiFetch<DocumentVersion>(`${BASE}/document-versions/${versionId}/retry-pdf/`, {
        method: "POST",
      }),
    onSuccess: (version) => invalidateGeneration(client, version),
  });
}

export function useConsultations(versionId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.consultations(versionId),
    queryFn: () =>
      apiFetch<Page<Consultation>>(`${BASE}/document-versions/${versionId}/consultations/`),
    enabled: versionId !== undefined,
  });
}

async function save(path: string, signal?: AbortSignal): Promise<void> {
  const { blob, filename } = await apiDownload(path, signal);
  downloadBlob(blob, filename);
}

export function downloadVersion(id: string, format: FormatFichier): Promise<void> {
  return save(`${BASE}/document-versions/${id}/download/${toQuery({ format })}`);
}

export function downloadTemplate(id: string, signal?: AbortSignal): Promise<void> {
  return save(`${BASE}/templates/${id}/file/`, signal);
}

export function previewTemplate(
  id: string,
  format: FormatFichier,
  signal?: AbortSignal,
): Promise<void> {
  return save(`${BASE}/templates/${id}/preview/${toQuery({ format })}`, signal);
}
