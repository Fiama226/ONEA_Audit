import type { Etape, Mission } from "../types";
import { GenericZone } from "./GenericZone";

/** Étape IV : squelette, rempli par la tâche T8. */
export function StepIVZone(props: { mission: Mission; step: Etape }) {
  return <GenericZone {...props} />;
}
