import { fr } from "@/i18n/fr";
import {
  baseUrl,
  ensureCsrfToken,
  isCsrfFailure,
  notifyUnauthorized,
  prepareCsrfReplay,
} from "./client";
import { ApiError, isApiError } from "./errors";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fieldErrors(body: Record<string, unknown>): Record<string, string[]> {
  const source = isRecord(body.errors)
    ? body.errors
    : Object.fromEntries(Object.entries(body).filter(([key]) => key !== "detail"));
  const out: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(source)) {
    if (Array.isArray(messages)) out[field] = messages.map(String);
    else if (typeof messages === "string") out[field] = [messages];
  }
  return out;
}

const STATUS_DETAIL: Record<number, string> = {
  401: fr.errors.unauthorized,
  403: fr.errors.forbidden,
  429: fr.errors.tooManyRequests,
};

function toError(xhr: XMLHttpRequest): ApiError {
  if (xhr.status === 413) return new ApiError(413, fr.errors.fileTooLarge);
  let body: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(xhr.responseText);
    if (isRecord(parsed)) body = parsed;
  } catch {
    // corps non JSON (page HTML d'un proxy) : message générique
  }
  const fallback = STATUS_DETAIL[xhr.status] ?? fr.errors.generic;
  const detail = typeof body.detail === "string" ? body.detail : fallback;
  return new ApiError(xhr.status, detail, fieldErrors(body));
}

/**
 * Envoi multipart avec progression (XHR : `fetch` n'expose pas la progression d'envoi).
 * `onProgress` reçoit un ratio entre 0 et 1 ; l'annulation par `signal` rejette en `AbortError`.
 * Même session et mêmes règles que `apiFetch` : cookie de session, en-tête X-CSRFToken, 401
 * signalé au gestionnaire de session, et un seul rejeu après un refus pour jeton CSRF périmé
 * (jeton redemandé, session vérifiée : même agent).
 */
export async function uploadWithProgress<T>(
  url: string,
  form: FormData,
  onProgress: (ratio: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  try {
    return await sendOnce<T>(url, form, onProgress, signal);
  } catch (e) {
    if (!isApiError(e) || !isCsrfFailure(e)) throw e;
    await prepareCsrfReplay();
    onProgress(0);
    return sendOnce<T>(url, form, onProgress, signal);
  }
}

async function sendOnce<T>(
  url: string,
  form: FormData,
  onProgress: (ratio: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  const csrf = await ensureCsrfToken();
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${baseUrl()}${url}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("X-CSRFToken", csrf);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        if (xhr.status === 401) notifyUnauthorized(url);
        reject(toError(xhr));
        return;
      }
      onProgress(1);
      try {
        resolve(JSON.parse(xhr.responseText) as T);
      } catch {
        reject(new ApiError(xhr.status, fr.errors.generic));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, fr.errors.network));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(form);
  });
}
