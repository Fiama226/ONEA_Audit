import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Page du rapport de la mission (squelette ; contenu : T15). */
export function RapportPage() {
  return <ZoneSkeleton id="rapportpage" title={fr.communication.reportPageTitle} />;
}
