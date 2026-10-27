import { fr } from "@/i18n/fr";
import { ApiError } from "./errors";

type TokenProvider = () => string | null | undefined;

let getAccessToken: TokenProvider = () => null;

/** Injecte la source du jeton d'accès (OIDC en production, session locale en dev). */
export function setTokenProvider(fn: TokenProvider): void {
  getAccessToken = fn;
}

function baseUrl(): string {
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

async function toApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const body = isRecord(payload) ? payload : {};
  const detail = typeof body.detail === "string" ? body.detail : fr.errors.generic;
  // DRF renvoie soit {errors: {...}} (gestionnaire personnalisé) soit {champ: [...]}.
  const errors =
    "errors" in body
      ? toFieldErrors(body.errors)
      : toFieldErrors(Object.fromEntries(Object.entries(body).filter(([k]) => k !== "detail")));
  return new ApiError(response.status, detail, errors);
}

export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  headers.set("Accept", "application/json");
  if (json !== undefined) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${baseUrl()}${path}`, {
    ...rest,
    headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
