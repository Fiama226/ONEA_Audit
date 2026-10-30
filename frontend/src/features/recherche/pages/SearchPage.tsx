import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Squelette T12 : page de recherche, à implémenter par T14. */
export function SearchPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">{fr.suivi.searchTitle}</h1>
      <ZoneSkeleton id="search-results" title={fr.suivi.skeletonSearch} />
    </>
  );
}
