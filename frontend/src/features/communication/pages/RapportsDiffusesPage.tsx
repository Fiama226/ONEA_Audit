import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Rapports diffusés visibles de l'utilisateur (squelette ; contenu : T15). */
export function RapportsDiffusesPage() {
  return <ZoneSkeleton id="rapportsdiffusespage" title={fr.communication.distributedTitle} />;
}
