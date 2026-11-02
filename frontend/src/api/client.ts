import { fr } from "@/i18n/fr";
import { ApiError } from "./errors";

type TokenProvider = () => string | null | undefined;

let getAccessToken: TokenProvider = () => null;

/** Injecte la source du jeton d'accès (jeton Bearer Keycloak via OIDC ; la SPA n'utilise pas d'autre authentification). */
export function setTokenProvider(fn: TokenProvider): void {
  getAccessToken = fn;
}

/** Jeton courant (pour les envois XHR qui ne passent pas par fetch). */
export function currentToken(): string | null {
  return getAccessToken() ?? null;
}

type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

/**
 * Enregistre la réaction à un 401 reçu en cours d'utilisation (jeton révoqué ou session
 * terminée ailleurs) : l'application ramène alors vers la connexion au lieu d'afficher des erreurs.
 */
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  onUnauthorized = fn;
}

/** Appels pour lesquels un 401 ne signifie pas « session expirée » (la fin de session elle-même). */
const SANS_REDIRECTION_401 = ["/api/v1/session/fin/"];

export function baseUrl(): string {
  const url = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";
  return url.replace(/\/+$/, "");
}

export type ApiInit = RequestInit & { json?: unknown };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toFieldErrors(value: unknown): Record<string, string[]> {
  if (!isRecord(value)) return {};
  const out: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(value)) {
    if (Array.isArray(messages)) out[field] = messages.map(String);
    else if (typeof messages === "string") out[field] = [messages];
  }
  return out;
}

const STATUS_DETAIL: Record<number, string> = {
  401: fr.errors.unauthorized,
  403: fr.errors.forbidden,
  404: fr.errors.notFound,
  429: fr.errors.tooManyRequests,
};

async function toApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const body = isRecord(payload) ? payload : {};
  const fallback = STATUS_DETAIL[response.status] ?? fr.errors.generic;
  const detail = typeof body.detail === "string" ? body.detail : fallback;
  // DRF renvoie soit {errors: {...}} (gestionnaire personnalisé) soit {champ: [...]}.
  const errors =
    "errors" in body
      ? toFieldErrors(body.errors)
      : toFieldErrors(Object.fromEntries(Object.entries(body).filter(([k]) => k !== "detail")));
  return new ApiError(response.status, detail, errors);
}

/** Requête authentifiée ; toute réponse non 2xx ou erreur réseau devient une ApiError. */
async function send(path: string, init: ApiInit, accept: string): Promise<Response> {
  const { json, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  headers.set("Accept", accept);
  if (json !== undefined) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...rest,
      headers,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    // Annulation voulue par l'appelant (AbortSignal) : ce n'est pas une panne réseau.
    if (rest.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    throw new ApiError(0, fr.errors.network);
  }

  if (!response.ok) {
    if (response.status === 401 && !SANS_REDIRECTION_401.includes(path)) onUnauthorized?.();
    throw await toApiError(response);
  }
  return response;
}

/** Nom renvoyé quand le serveur n'indique aucun nom de fichier (ou que CORS le masque). */
export const DEFAULT_DOWNLOAD_NAME = "export";
const DEFAULT_FILENAME = DEFAULT_DOWNLOAD_NAME;

/** Retire chemin et caractères de contrôle d'un nom reçu du serveur. */
function sanitizeFilename(name: string): string {
  const printable = [...name].filter((c) => c.charCodeAt(0) > 0x1f && c.charCodeAt(0) !== 0x7f);
  const base = printable.join("").split(/[\\/]/).pop() ?? "";
  const cleaned = base.trim().replace(/^\.+/, "");
  return cleaned || DEFAULT_FILENAME;
}

/** Nom de fichier de l'en-tête Content-Disposition ; `filename*=UTF-8''` est prioritaire. */
function filenameFrom(disposition: string | null): string {
  return sanitizeFilename(rawFilenameFrom(disposition));
}

function rawFilenameFrom(disposition: string | null): string {
  if (!disposition) return DEFAULT_FILENAME;
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      // encodage invalide : repli sur filename=
    }
  }
  const plain = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(disposition);
  const name = (plain?.[1] ?? plain?.[2] ?? "").trim();
  return name || DEFAULT_FILENAME;
}

/** Télécharge un fichier (export CSV / Excel) avec le même jeton et les mêmes erreurs que apiFetch. */
export async function apiDownload(
  path: string,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string }> {
  const response = await send(path, { signal }, "*/*");
  return {
    blob: await response.blob(),
    filename: filenameFrom(response.headers.get("Content-Disposition")),
  };
}

/** Envoi multipart (dépôt de fichier) : même jeton et mêmes erreurs, sans en-tête Content-Type. */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  signal?: AbortSignal,
): Promise<T> {
  // Pas de Content-Type : le navigateur y ajoute la frontière multipart.
  const response = await send(path, { method: "POST", body: formData, signal }, "application/json");
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, fr.errors.generic);
  }
}

export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const response = await send(path, init, "application/json");
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    // 2xx non JSON (ex. page HTML d'un mauvais VITE_API_URL)
    throw new ApiError(response.status, fr.errors.generic);
  }
}
