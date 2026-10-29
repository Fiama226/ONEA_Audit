import type { Etape, Mission } from "../types";
import { GenericZone } from "./GenericZone";

/** Étape II : squelette, rempli par la tâche T8. */
export function StepIIZone(props: { mission: Mission; step: Etape }) {
  return <GenericZone {...props} />;
}
