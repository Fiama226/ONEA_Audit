import type { components } from "@/api/schema";

type S = components["schemas"];

/** Fixtures typées : recopiées de `backend/tests/recherche/contrat_lot8.json` (lot 8 T11). */
export const resultatFixture = {
  type: "ACTION",
  objet_id: "55555555-5555-4555-8555-555555555555",
  mission_id: "11111111-1111-4111-8111-111111111111",
  mission_reference: "MI-2026-001",
  titre: "Formaliser le rapprochement mensuel",
  sous_titre: "Fatou Koné",
  // \u0002 et \u0003 encadrent les termes trouvés (jamais de HTML).
  extrait: "Formaliser le \u0002rapprochement\u0003 mensuel",
  etape: null,
} satisfies S["ResultatRecherche"];

export const reponseRechercheFixture = {
  resultats: [resultatFixture],
  plus: false,
  degrade: false,
} satisfies S["ReponseRecherche"];
