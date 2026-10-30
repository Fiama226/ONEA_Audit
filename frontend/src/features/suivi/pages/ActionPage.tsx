import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Squelette T12 : page de suivi d'une action, à implémenter par T13. */
export function ActionPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">{fr.suivi.actionTitle}</h1>
      <ZoneSkeleton id="suivi-action" title={fr.suivi.skeletonAction} />
    </>
  );
}
