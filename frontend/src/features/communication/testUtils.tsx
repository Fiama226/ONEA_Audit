import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { MISSION_ID, pageOf } from "@/features/missions/testUtils";
import { authValueFor } from "@/test/shell";
import type { Rapport, RapportDiffuse } from "./types";

export { MISSION_ID, pageOf };
export const RAPPORT_ID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa";
export const PROVISOIRE_ID = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb";

/** Rapport en brouillon, forme figée par le contrat du lot 7 (`Rapport`). */
export function aRapport(overrides: Partial<Rapport> = {}): Rapport {
  return {
    id: RAPPORT_ID,
    mission: MISSION_ID,
    numero_version: 1,
    corrige_de: null,
    motif_correction: "",
    statut: "BROUILLON",
    synthese: "",
    appreciation_globale: "",
    commentaire_appreciation: "",
    contexte: "",
    objectifs_texte: "",
    perimetre_texte: "",
    methodologie: "",
    conclusion: "",
    note_synthetique: "",
    annexes_texte: "",
    cycle: 0,
    soumis_par: null,
    soumis_le: null,
    empreinte_soumise: "",
    valide_par: null,
    valide_le: null,
    confirmation_validation: null,
    mode_signature: "",
    signature_electronique_requise: false,
    motif_renvoi: "",
    provisoire_courant: null,
    version_finale: null,
    diffusion: null,
    evenements: [],
    actions_possibles: [],
    ...overrides,
  } as Rapport;
}

export function aRapportDiffuse(overrides: Partial<RapportDiffuse> = {}): RapportDiffuse {
  return {
    id: RAPPORT_ID,
    mission_reference: "MI-2026-001",
    mission_titre: "Audit des achats",
    numero_version: 1,
    numero_document: "RA-2026-001",
    valide_le: "2026-10-28T09:00:00Z",
    diffuse_le: "2026-10-29T09:00:00Z",
    synthese: "Le dispositif d'achat est perfectible.",
    appreciation_globale: "PERFECTIBLE",
    mention_correction: "",
    mon_accuse_reception: null,
    actions_possibles: [],
    ...overrides,
  } as RapportDiffuse;
}

/** Rend `ui` avec client de requêtes, authentification et routeur pour un rôle donné. */
export function renderCommunication(ui: ReactElement, role: Role = "AUDITEUR") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role, vi.fn())}>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, client };
}
