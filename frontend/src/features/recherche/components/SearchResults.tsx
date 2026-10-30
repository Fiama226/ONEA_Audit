import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { Highlight } from "@/lib/highlight";
import type { ReponseRecherche, TypeResultat } from "../api";
import { routeFor } from "../routes";
import { SEARCH_TYPES } from "./TypeFilter";

/** Résultats groupés par type (`h2`) ; titre et extrait passent par `Highlight` (jamais de HTML). */
export function SearchResults({ response }: { response: ReponseRecherche }) {
  const groups = SEARCH_TYPES.map((type: TypeResultat) => ({
    type,
    hits: response.resultats.filter((r) => r.type === type),
  })).filter((g) => g.hits.length > 0);

  if (groups.length === 0) {
    return <p className="text-sm text-text-muted">{fr.suivi.searchNone}</p>;
  }
  return (
    <div className="flex flex-col gap-6">
      {groups.map(({ type, hits }) => (
        <section key={type} aria-labelledby={`search-group-${type}`}>
          <h2 id={`search-group-${type}`} className="mb-2 text-lg font-semibold">
            {fr.suivi[`search${type}` as const]}
          </h2>
          <ul className="divide-y divide-border rounded-md border border-border bg-surface">
            {hits.map((hit) => (
              <li key={`${hit.type}-${hit.objet_id}`}>
                <Link
                  to={routeFor(hit)}
                  className="flex flex-col gap-0.5 px-4 py-3 hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <span className="font-medium">
                    <Highlight text={hit.titre} />
                  </span>
                  {hit.sous_titre && (
                    <span className="text-sm text-text-muted">{hit.sous_titre}</span>
                  )}
                  {hit.extrait && (
                    <span className="text-sm text-text-muted">
                      <Highlight text={hit.extrait} />
                    </span>
                  )}
                  {hit.mission_reference && (
                    <span className="text-xs text-text-muted">
                      {fr.rechercheNotifications.searchMission.replace(
                        "{ref}",
                        hit.mission_reference,
                      )}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {response.plus && (
        <p role="status" className="text-sm text-text-muted">
          {fr.suivi.searchMore}
        </p>
      )}
    </div>
  );
}
