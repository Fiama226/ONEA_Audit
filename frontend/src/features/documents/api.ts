import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";
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

export function useDocumentTypes() {
  return useQuery({
    queryKey: documentKeys.types(),
    queryFn: () => apiFetch<DocumentType[]>(`${BASE}/document-types/`),
  });
}

export function useTemplates(params: TemplateParams = {}) {
  return useQuery({
    queryKey: documentKeys.templateList(params),
    queryFn: () => apiFetch<Page<Gabarit>>(`${BASE}/templates/${toQuery(params)}`),
  });
}

export function useTemplate(id: string | undefined) {
  return useQuery({
    queryKey: documentKeys.template(id),
    queryFn: () => apiFetch<Gabarit>(`${BASE}/templates/${id}/`),
    enabled: id !== undefined,
  });
}

export type UploadTemplateInput = { type_document: string; fichier: File; commentaire?: string };

export function useUploadTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: UploadTemplateInput) => {
      const body = new FormData();
      body.append("type_document", input.type_document);
      body.append("fichier", input.fichier);
      body.append("commentaire", input.commentaire ?? "");
      return apiUpload<Gabarit>(`${BASE}/templates/`, body);
    },
    onSuccess: () => invalidate(client, documentKeys.templates(), documentKeys.types()),
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
    mutationFn: (data: ApercuFormat) =>
      apiFetch<ApercuNumero>(`${BASE}/numbering-formats/preview/`, { method: "POST", json: data }),
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

export function useAvailableDocuments(missionId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.available(missionId),
    queryFn: () =>
      apiFetch<DocumentDisponible[]>(
        `${BASE}/documents/available/${toQuery({ mission: missionId })}`,
      ),
    enabled: missionId !== undefined,
    // Génération Word ou PDF en cours : le statut est relu toutes les 2 s.
    refetchInterval: (q) =>
      q.state.data?.some(
        (d) =>
          d.en_cours || (d.document?.derniere_version && isInProgress(d.document.derniere_version)),
      )
        ? POLL_INTERVAL_MS
        : false,
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
  const [timedOut, setTimedOut] = useState(false);
  const query = useQuery({
    queryKey: documentKeys.version(id),
    queryFn: () => apiFetch<DocumentVersion>(`${BASE}/document-versions/${id}/`),
    enabled: id !== undefined,
    refetchInterval: (q) => {
      const data = q.state.data;
      return data && isInProgress(data) && !timedOut ? POLL_INTERVAL_MS : false;
    },
  });
  const polling = query.data !== undefined && isInProgress(query.data);
  useEffect(() => {
    if (!polling) return;
    const timer = setTimeout(() => setTimedOut(true), POLL_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [polling, id]);
  const timeoutError = timedOut && polling ? new ApiError(0, GENERATION_TIMEOUT_MESSAGE) : null;
  return Object.assign(query, { timeoutError });
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

async function save(path: string): Promise<void> {
  const { blob, filename } = await apiDownload(path);
  downloadBlob(blob, filename);
}

export function downloadVersion(id: string, format: FormatFichier): Promise<void> {
  return save(`${BASE}/document-versions/${id}/download/${toQuery({ format })}`);
}

export function downloadTemplate(id: string): Promise<void> {
  return save(`${BASE}/templates/${id}/file/`);
}

export function previewTemplate(id: string, format: FormatFichier): Promise<void> {
  return save(`${BASE}/templates/${id}/preview/${toQuery({ format })}`);
}
