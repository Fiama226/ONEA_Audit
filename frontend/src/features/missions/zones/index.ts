import type { ComponentType } from "react";
import { createElement } from "react";
import { StepIIIAnalyse } from "@/features/analyse/zones/StepIIIAnalyse";
import { StepVIIZone } from "@/features/analyse/zones/StepVIIZone";
import { StepVIZone } from "@/features/analyse/zones/StepVIZone";
import { StepVZone } from "@/features/analyse/zones/StepVZone";
import { StepIXZone } from "@/features/accomplissement/zones/StepIXZone";
import { StepVIIIZone } from "@/features/accomplissement/zones/StepVIIIZone";
import { StepXIIIZone } from "@/features/accomplissement/zones/StepXIIIZone";
import { StepXIIZone } from "@/features/accomplissement/zones/StepXIIZone";
import { StepXZone } from "@/features/accomplissement/zones/StepXZone";
import { StepXVIIIZone } from "@/features/communication/zones/StepXVIIIZone";
import { StepXVIIZone } from "@/features/communication/zones/StepXVIIZone";
import { StepXVZone } from "@/features/communication/zones/StepXVZone";
import { StepXIVZone } from "@/features/constats/zones/StepXIVZone";
import { StepXVIZone } from "@/features/recommandations/zones/StepXVIZone";
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
  8: StepVIIIZone,
  9: StepIXZone,
  10: StepXZone,
  12: StepXIIZone,
  13: StepXIIIZone,
  14: StepXIVZone,
  15: StepXVZone,
  16: StepXVIZone,
  17: StepXVIIZone,
  18: StepXVIIIZone,
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
