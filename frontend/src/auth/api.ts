import { apiFetch } from "@/api/client";
import type { EtatSession } from "./types";

/*
 * Hand-typed calls to /api/v1/auth/ (the committed schema.d.ts predates these endpoints; it is
 * regenerated in a later task). Field names follow backend/apps/users/auth_serializers.py.
 */
const AUTH = "/api/v1/auth";

export function fetchSession(): Promise<EtatSession> {
  return apiFetch<EtatSession>(`${AUTH}/session/`);
}

export function postLogin(identifiant: string, motDePasse: string): Promise<EtatSession> {
  return apiFetch<EtatSession>(`${AUTH}/login/`, {
    method: "POST",
    json: { identifiant, mot_de_passe: motDePasse },
  });
}

export function postLoginOtp(code: string): Promise<EtatSession> {
  return apiFetch<EtatSession>(`${AUTH}/login/otp/`, { method: "POST", json: { code } });
}

export function postLogout(signal?: AbortSignal): Promise<void> {
  return apiFetch<void>(`${AUTH}/logout/`, { method: "POST", signal });
}

export function postPasswordChange(ancien: string, nouveau: string): Promise<EtatSession> {
  return apiFetch<EtatSession>(`${AUTH}/password/change/`, {
    method: "POST",
    json: { ancien, nouveau },
  });
}

/** Always 202 with the same neutral body, whether the account exists or not. */
export function postPasswordForgot(identifiant: string): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>(`${AUTH}/password/forgot/`, {
    method: "POST",
    json: { identifiant },
  });
}

export function postPasswordReset(data: {
  identifiant: string;
  code: string;
  nouveau_mot_de_passe: string;
}): Promise<void> {
  return apiFetch<void>(`${AUTH}/password/reset/`, { method: "POST", json: data });
}
