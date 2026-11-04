import { apiFetch } from "@/api/client";
import type { components } from "@/api/schema";
import type { EtatSession } from "./types";

/** Calls to /api/v1/auth/, typed from the generated OpenAPI schema. */
type S = components["schemas"];

const AUTH = "/api/v1/auth";

export function fetchSession(): Promise<EtatSession> {
  return apiFetch<EtatSession>(`${AUTH}/session/`);
}

export function postLogin(identifiant: string, motDePasse: string): Promise<EtatSession> {
  const json: S["ConnexionRequest"] = { identifiant, mot_de_passe: motDePasse };
  return apiFetch<EtatSession>(`${AUTH}/login/`, { method: "POST", json });
}

export function postLoginOtp(code: string): Promise<EtatSession> {
  const json: S["CodeConnexionRequest"] = { code };
  return apiFetch<EtatSession>(`${AUTH}/login/otp/`, { method: "POST", json });
}

export function postLogout(signal?: AbortSignal): Promise<void> {
  return apiFetch<void>(`${AUTH}/logout/`, { method: "POST", signal });
}

export function postPasswordChange(ancien: string, nouveau: string): Promise<EtatSession> {
  const json: S["ChangementMotDePasseRequest"] = { ancien, nouveau };
  return apiFetch<EtatSession>(`${AUTH}/password/change/`, { method: "POST", json });
}

/** Always 202 with the same neutral body, whether the account exists or not. */
export function postPasswordForgot(identifiant: string): Promise<S["Message"]> {
  const json: S["MotDePasseOublieRequest"] = { identifiant };
  return apiFetch<S["Message"]>(`${AUTH}/password/forgot/`, { method: "POST", json });
}

export function postPasswordReset(data: S["ReinitialisationRequest"]): Promise<void> {
  return apiFetch<void>(`${AUTH}/password/reset/`, { method: "POST", json: data });
}
