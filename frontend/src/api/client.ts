import { fr } from "@/i18n/fr";
import { ApiError } from "./errors";

/*
 * Authentification par cookie de session (HttpOnly, posé par POST /api/v1/auth/login/) :
 * toute requête part avec `credentials: "include"` et aucune n'a d'en-tête Authorization.
 * Les écritures portent l'en-tête X-CSRFToken ; le jeton est lu sur GET /api/v1/auth/csrf/
 * (le cookie CSRF est HttpOnly en production, donc illisible en JavaScript).
 */

export const CSRF_PATH = "/api/v1/auth/csrf/";
const CSRF_HEADER = "X-CSRFToken";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

let csrfToken: string | null = null;
let csrfPending: Promise<string> | null = null;
let csrfGeneration = 0;

/**
 * Oublie le jeton CSRF : la prochaine écriture le redemande. À appeler après chaque changement
 * de session (connexion, code, changement de mot de passe, déconnexion, expiration), car le
 * serveur renouvelle alors le jeton.
 */
export function resetCsrfToken(): void {
  csrfToken = null;
  csrfPending = null;
  csrfGeneration += 1;
}

/** Jeton CSRF courant, demandé au serveur au premier besoin ; une seule demande à la fois. */
export function ensureCsrfToken(): Promise<string> {
  if (csrfToken !== null) return Promise.resolve(csrfToken);
  if (csrfPending) return csrfPending;
  const generation = csrfGeneration;
  const pending = loadCsrfToken()
    .then((token) => {
      // Un reset pendant la demande rend ce jeton caduc : il n'est pas mémorisé.
      if (generation === csrfGeneration) csrfToken = token;
      return token;
    })
    .finally(() => {
      if (csrfPending === pending) csrfPending = null;
    });
  csrfPending = pending;
  return pending;
}

async function loadCsrfToken(): Promise<string> {
  const response = await send(CSRF_PATH, {}, "application/json");
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const token = isRecord(body) ? body.csrf_token : undefined;
  if (typeof token !== "string" || token === "") {
    throw new ApiError(response.status, fr.errors.generic);
  }
  return token;
}

type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

/**
 * Enregistre la réaction à un 401 reçu en cours d'utilisation (session expirée ou terminée
 * ailleurs) : l'application ramène alors vers la connexion au lieu d'afficher des erreurs.
 */
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  onUnauthorized = fn;
}

/**
 * Appels pour lesquels un 401 ne signifie pas « session expirée » : sonde de session d'un
 * anonyme, échec de connexion ou de code, déconnexion, mot de passe oublié.
 */
const SANS_REDIRECTION_401 = new Set([
  CSRF_PATH,
  "/api/v1/auth/session/",
  "/api/v1/auth/login/",
  "/api/v1/auth/login/otp/",
  "/api/v1/auth/logout/",
  "/api/v1/auth/password/forgot/",
  "/api/v1/auth/password/reset/",
]);

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

/**
 * Requête avec le cookie de session (et le jeton CSRF pour une écriture) ; toute réponse non
 * 2xx ou erreur réseau devient une ApiError.
 */
async function send(path: string, init: ApiInit, accept: string): Promise<Response> {
  const { json, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  headers.set("Accept", accept);
  if (json !== undefined) headers.set("Content-Type", "application/json");
  const method = (rest.method ?? "GET").toUpperCase();
  if (!SAFE_METHODS.has(method)) headers.set(CSRF_HEADER, await ensureCsrfToken());

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...rest,
      headers,
      credentials: "include",
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    // Annulation voulue par l'appelant (AbortSignal) : ce n'est pas une panne réseau.
    if (rest.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    throw new ApiError(0, fr.errors.network);
  }

  if (!response.ok) {
    if (response.status === 401 && !SANS_REDIRECTION_401.has(path)) onUnauthorized?.();
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

/** Télécharge un fichier (export CSV / Excel) avec la même session et les mêmes erreurs que apiFetch. */
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

/** Envoi multipart (dépôt de fichier) : même session, jeton CSRF et mêmes erreurs, sans en-tête Content-Type. */
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
