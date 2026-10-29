import type { Etape, Mission } from "../types";
import { GenericZone } from "./GenericZone";

/** Étape III : squelette, rempli par la tâche T8. */
export function StepIIIZone(props: { mission: Mission; step: Etape }) {
  return <GenericZone {...props} />;
}
