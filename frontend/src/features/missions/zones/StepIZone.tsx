import type { Etape, Mission } from "../types";
import { GenericZone } from "./GenericZone";

/** Étape I : squelette, rempli par la tâche T8. */
export function StepIZone(props: { mission: Mission; step: Etape }) {
  return <GenericZone {...props} />;
}
