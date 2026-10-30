import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Plan d'actions de la mission (squelette ; contenu : T14). */
export function PlanActionsPage() {
  return <ZoneSkeleton id="planactionspage" title={fr.communication.planActionsTitle} />;
}
