import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Réponses de l'audité au rapport provisoire (squelette ; contenu : T13). */
export function ReponsesProvisoirePage() {
  return <ZoneSkeleton id="reponsesprovisoirepage" title={fr.communication.draftResponsesTitle} />;
}
