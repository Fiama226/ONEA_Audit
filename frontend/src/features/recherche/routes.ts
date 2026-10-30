import type { components } from "@/api/schema";

export type ResultatRecherche = components["schemas"]["ResultatRecherche"];

/**
 * Destination d'un résultat de recherche. Un identifiant de mission manquant (objet sans mission)
 * renvoie vers le registre ou l'accueil plutôt que vers un chemin invalide.
 */
export function routeFor(
  hit: Pick<ResultatRecherche, "type" | "objet_id" | "mission_id" | "etape">,
): string {
  const { type, objet_id: id, mission_id: mid, etape } = hit;
  switch (type) {
    case "MISSION":
      return `/missions/${id}`;
    case "CONSTAT":
      return mid ? `/missions/${mid}/constats/${id}` : "/missions";
    case "RECOMMANDATION":
      return `/recommandations?recommandation=${id}`;
    case "ACTION":
      return `/recommandations/actions/${id}`;
    case "DOCUMENT":
      return mid ? `/missions/${mid}/etapes/${etape ?? 1}` : "/documents";
  }
}
