import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Lecture d'un rapport diffusé (squelette ; contenu : T15). */
export function RapportDiffusePage() {
  return <ZoneSkeleton id="rapportdiffusepage" title={fr.communication.distributedDetailTitle} />;
}
