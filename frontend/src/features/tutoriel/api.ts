import { apiFetch } from "@/api/client";
import type { components } from "@/api/schema";

export type TutorielEtat = components["schemas"]["Tutoriel"];
export type TutorielAction = components["schemas"]["ActionTutorielEnum"];

/** Enregistrement de l'état du tutoriel (contrat : POST /api/v1/me/tutoriel/). */
export const TUTORIEL_URL = "/api/v1/me/tutoriel/";

export function envoyerAction(action: TutorielAction, version: number): Promise<TutorielEtat> {
  return apiFetch<TutorielEtat>(TUTORIEL_URL, { method: "POST", json: { action, version } });
}
