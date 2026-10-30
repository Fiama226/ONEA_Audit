import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";

/** Étape XVIII : validation et diffusion du rapport (squelette ; contenu : T15). */
export function StepXVIIIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XVIII-${step.id}`} title={fr.communication.zoneXVIIITitle} />;
}
