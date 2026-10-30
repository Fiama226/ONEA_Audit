import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";

/** Étape XVII : rédaction du rapport (squelette ; contenu : T15). */
export function StepXVIIZone({ step }: ZoneProps) {
  return <ZoneSkeleton id={`zone-XVII-${step.id}`} title={fr.communication.zoneXVIITitle} />;
}
