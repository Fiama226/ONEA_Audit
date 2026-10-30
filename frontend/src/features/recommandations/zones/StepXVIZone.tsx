import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";

/** Étape XVI : plan d'actions (squelette ; contenu : T14). */
export function StepXVIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XVI-${step.id}`} title={fr.communication.zoneXVITitle} />;
}
