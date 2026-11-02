import type { DocumentType, FormatNumerotation, Gabarit } from "../types";

export const TYPE_CODE = "ORDRE_MISSION";

export function aType(overrides: Partial<DocumentType> = {}): DocumentType {
  return {
    code: TYPE_CODE,
    libelle: "Ordre de mission",
    etape: 4,
    etape_romain: "IV",
    contrat_version: 1,
    champs: [
      {
        nom: "mission",
        type: "bloc",
        description: "La mission",
        enfants: [{ nom: "titre", type: "texte", description: "Titre de la mission", enfants: [] }],
      },
      {
        nom: "ordre",
        type: "bloc",
        description: "L'ordre",
        enfants: [{ nom: "equipe", type: "liste", description: "Équipe", enfants: [] }],
      },
    ],
    gabarit_actif: {
      id: "g2",
      version: 2,
      statut: "ACTIF",
      provisoire: true,
      active_le: "2026-03-05T09:00:00Z",
    },
    format_numerotation: aFormat(),
    ...overrides,
  } as DocumentType;
}

export function aFormat(overrides: Partial<FormatNumerotation> = {}): FormatNumerotation {
  return {
    type_document: TYPE_CODE,
    modele: "{mission}/{code}-{sequence}",
    portee: "MISSION",
    abreviation: "OM",
    apercu: "MI-2026-001/OM-01",
    ...overrides,
  } as FormatNumerotation;
}

export function aTemplate(overrides: Partial<Gabarit> = {}): Gabarit {
  return {
    id: "g1",
    type_document: TYPE_CODE,
    type_document_libelle: "Ordre de mission",
    version: 1,
    statut: "DEPOSE",
    nom_original: "om-v1.docx",
    taille: 20480,
    empreinte: "a".repeat(64),
    balises: [],
    contrat_version: 1,
    provisoire: false,
    commentaire: "Première version",
    created_by: null,
    created_at: "2026-03-01T09:00:00Z",
    active_par: null,
    active_le: null,
    ...overrides,
  } as Gabarit;
}
