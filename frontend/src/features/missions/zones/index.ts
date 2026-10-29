import type { ComponentType } from "react";
import type { Etape, Mission } from "../types";
import { StepIIIZone } from "./StepIIIZone";
import { StepIIZone } from "./StepIIZone";
import { StepIVZone } from "./StepIVZone";
import { StepIZone } from "./StepIZone";

export type ZoneProps = { mission: Mission; step: Etape };

/** Zone de travail par numéro d'étape ; les étapes sans zone propre utilisent `GenericZone`. */
export const ZONES: Record<number, ComponentType<ZoneProps>> = {
  1: StepIZone,
  2: StepIIZone,
  3: StepIIIZone,
  4: StepIVZone,
};
