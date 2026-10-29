import type { ComponentType } from "react";
import { createElement } from "react";
import { StepIIIAnalyse } from "@/features/analyse/zones/StepIIIAnalyse";
import { StepVIIZone } from "@/features/analyse/zones/StepVIIZone";
import { StepVIZone } from "@/features/analyse/zones/StepVIZone";
import { StepVZone } from "@/features/analyse/zones/StepVZone";
import type { Etape, Mission } from "../types";
import { StepIIIZone } from "./StepIIIZone";
import { StepIIZone } from "./StepIIZone";
import { StepIVZone } from "./StepIVZone";
import { StepIZone } from "./StepIZone";

export type ZoneProps = { mission: Mission; step: Etape };

/**
 * Zone de travail par numéro d'étape ; les étapes sans zone propre utilisent `GenericZone`.
 * Extensible : les lots suivants ajoutent leurs zones ici.
 */
export const ZONES: Record<number, ComponentType<ZoneProps>> = {
  1: StepIZone,
  2: StepIIZone,
  3: StepIIIZone,
  4: StepIVZone,
  5: StepVZone,
  6: StepVIZone,
  7: StepVIIZone,
};

/** Compléments insérés dans la zone d'une étape par un autre lot (lots 5, 6 et 7). */
export const ZONE_COMPLEMENTS: Partial<Record<number, ComponentType<ZoneProps>>> = {
  3: StepIIIAnalyse,
};

/** Rend le complément de l'étape `numero` s'il existe, sinon rien. */
export function ZoneComplement({ numero, mission, step }: ZoneProps & { numero: number }) {
  const Complement = ZONE_COMPLEMENTS[numero];
  return Complement ? createElement(Complement, { mission, step }) : null;
}
