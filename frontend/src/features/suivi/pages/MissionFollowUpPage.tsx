import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Squelette T12 : suivi des recommandations d'une mission, à implémenter par T13. */
export function MissionFollowUpPage() {
  return (
    <>
      <h2 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">
        {fr.suivi.missionFollowUpTitle}
      </h2>
      <ZoneSkeleton id="suivi-mission" title={fr.suivi.skeletonMission} />
    </>
  );
}
