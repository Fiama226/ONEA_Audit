import { z } from "zod";
import { riskLevel } from "@/components/RiskMatrix";
import { fr } from "@/i18n/fr";
import type { NiveauRisque, PrioriteRisque } from "../types";

const c = fr.refCartographie;

const scale = z.string().regex(/^[1-5]$/, c.invalidScale);

export const riskSchema = z.object({
  processus: z.string().min(1, c.requiredProcessus),
  objet_auditable: z.string(),
  libelle: z.string().trim().min(1, c.requiredLibelleRisque).max(500, c.maxLibelle),
  description: z.string(),
  probabilite: scale,
  impact: scale,
  vulnerabilite: z.string(),
  reponse: z.string(),
  priorite: z.string(),
  objectif_controle: z.string(),
  dispositif_controle: z.string(),
});

export type RiskFormValues = z.infer<typeof riskSchema>;

const NIVEAUX: Record<ReturnType<typeof riskLevel>, NiveauRisque> = {
  low: "FAIBLE",
  medium: "MOYEN",
  high: "ELEVE",
};

/** Aperçu client uniquement : le serveur reste l'autorité pour le score et le niveau. */
export function niveauFromScore(score: number): NiveauRisque {
  return NIVEAUX[riskLevel(score)];
}

export function prioriteFromNiveau(niveau: NiveauRisque): PrioriteRisque {
  return niveau === "ELEVE" ? 1 : niveau === "MOYEN" ? 2 : 3;
}
