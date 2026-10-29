import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { authValueFor } from "@/test/shell";
import type { Document, DocumentDisponible, DocumentVersion } from "./types";

export const MISSION_ID = "11111111-1111-4111-8111-111111111111";
export const OBJET_ID = "33333333-3333-4333-8333-333333333333";
export const VERSION_ID = "44444444-4444-4444-8444-444444444444";
export const DOC_ID = "55555555-5555-4555-8555-555555555555";
export const HASH = "3f2a" + "0".repeat(56) + "9c1b";

export function aVersion(overrides: Partial<DocumentVersion> = {}): DocumentVersion {
  return {
    id: VERSION_ID,
    document: DOC_ID,
    numero_version: 1,
    statut: "PRETE",
    statut_pdf: "PRET",
    gabarit: { id: "66666666-6666-4666-8666-666666666666", version: 3, provisoire: true },
    demandee_par: {
      id: 1,
      username: "awa",
      nom_complet: "Awa Ouedraogo",
      role: "AUDITEUR",
      direction_code: "DAI",
      fonction: "Auditrice",
    },
    created_at: "2026-03-05T09:00:00Z",
    genere_le: "2026-03-05T09:00:30Z",
    pdf_le: "2026-03-05T09:01:00Z",
    empreinte_docx: HASH,
    empreinte_pdf: HASH,
    taille_docx: 1000,
    taille_pdf: 2000,
    erreur: "",
    erreur_pdf: "",
    confirmation: null,
    peut_relancer_pdf: false,
    ...overrides,
  } satisfies DocumentVersion;
}

export function aDocument(overrides: Partial<Document> = {}): Document {
  const version = aVersion();
  return {
    id: DOC_ID,
    type_document: "ORDRE_MISSION",
    type_document_libelle: "Ordre de mission",
    numero: "OM-2026-001",
    mission: { id: MISSION_ID, reference: "MI-2026-001", titre: "Audit des achats" },
    derniere_version: {
      id: version.id,
      numero_version: version.numero_version,
      statut: version.statut,
      statut_pdf: version.statut_pdf,
      genere_le: version.genere_le,
    },
    nombre_versions: 1,
    objet_id: OBJET_ID,
    versions: [version],
    ...overrides,
  } as Document;
}

export function aDisponible(overrides: Partial<DocumentDisponible> = {}): DocumentDisponible {
  return {
    type_document: "ORDRE_MISSION",
    libelle: "Ordre de mission",
    etape: 4,
    objet_id: OBJET_ID,
    document: null,
    peut_generer: true,
    raison: null,
    en_cours: false,
    ...overrides,
  } satisfies DocumentDisponible;
}

export function newClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/** Enveloppe de rendu : client TanStack Query et utilisateur authentifié. */
export function renderDocuments(ui: ReactElement, role: Role = "AUDITEUR") {
  const client = newClient();
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role)}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, client };
}

export function queryWrapper(client = newClient()) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, Wrapper };
}
