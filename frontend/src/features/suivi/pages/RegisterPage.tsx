import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Squelette T12 : registre des recommandations et des actions, à implémenter par T13. */
export function RegisterPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">{fr.suivi.registerTitle}</h1>
      <ZoneSkeleton id="suivi-register" title={fr.suivi.skeletonRegister} />
    </>
  );
}
