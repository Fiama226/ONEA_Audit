import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import * as download from "@/api/download";
import { ApiError } from "@/api/errors";
import { API_URL, server } from "@/test/msw";
import type { FicheDetail, Piece, TestPrevu } from "../types";
import { FichePage } from "./FichePage";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const MISSION = "11111111-1111-4111-8111-111111111111";
const FICHE = "22222222-2222-4222-8222-222222222222";
const TEST = "33333333-3333-4333-8333-333333333333";
const USER = {
  id: 2,
  username: "kone",
  nom_complet: "Awa Koné",
  role: "AUDITEUR",
  direction_code: "DAI",
  fonction: "Auditrice",
} as const;

function aPiece(overrides: Partial<Piece> = {}): Piece {
  return {
    id: "44444444-4444-4444-8444-444444444444",
    fiche: FICHE,
    numero: 1,
    libelle: "Facture 12",
    description: "",
    nom_fichier_original: "facture.pdf",
    type_mime: "application/pdf",
    taille_octets: 2048,
    empreinte_sha256: "abcdef0123456789".repeat(4),
    deposee_par: USER,
    deposee_le: "2026-05-04T09:00:00Z",
    actions_possibles: ["TELECHARGER"],
    ...overrides,
  } satisfies Piece;
}

function aFiche(overrides: Partial<FicheDetail> = {}): FicheDetail {
  return {
    id: FICHE,
    mission: MISSION,
    test: TEST,
    test_code: "T-001",
    test_libelle: "Rapprochement des factures",
    objectif_code: "OA-01",
    statut: "BROUILLON",
    auteur_detail: USER,
    date_realisation: null,
    travaux_realises: "",
    echantillon_teste: "",
    taille_testee: null,
    nombre_exceptions: null,
    resultat: "",
    conclusion: "",
    commentaire_conclusion: "",
    charge_reelle_jours: null,
    justification_sans_piece: "",
    soumise_par: null,
    soumise_le: null,
    validee_par: null,
    validee_le: null,
    motif_renvoi: "",
    constats: [],
    actions_possibles: ["MODIFIER", "SOUMETTRE", "DEPOSER_PIECE"],
    pieces: [],
    evenements: [],
    ...overrides,
  } satisfies FicheDetail;
}

function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

function setup({ fiche = aFiche(), pieces = [] as Piece[] } = {}) {
  const test = {
    id: TEST,
    objectif_test: "Vérifier les rapprochements",
    nature: "EXAMEN_DOCUMENTAIRE",
    procedure: "Rapprocher factures et bons",
    population: "Factures 2025",
    taille_echantillon: 30,
  } as TestPrevu;
  server.use(
    http.get(`${API_URL}/api/v1/test-sheets/${FICHE}/`, () => HttpResponse.json(fiche)),
    http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.json(page([test]))),
    http.get(`${API_URL}/api/v1/evidence/`, () => HttpResponse.json(page(pieces))),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/missions/${MISSION}/fiches/${FICHE}`]}>
        <Routes>
          <Route path="/missions/:id/fiches/:ficheId" element={<FichePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("FichePage", () => {
  it("affiche l'en-tête du test prévu", async () => {
    setup();
    expect(await screen.findByText("Rapprocher factures et bons")).toBeVisible();
    expect(screen.getByText("Vérifier les rapprochements")).toBeVisible();
    expect(screen.getByText("Examen documentaire")).toBeVisible();
    expect(screen.getByText("Factures 2025 · 30")).toBeVisible();
  });

  it("bloque la soumission sans conclusion, sans appeler le serveur", async () => {
    let called = false;
    server.use(
      http.post(`${API_URL}/api/v1/test-sheets/${FICHE}/submit/`, () => {
        called = true;
        return HttpResponse.json(aFiche());
      }),
    );
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: "Soumettre la fiche" }));
    expect(
      await screen.findByText("Choisissez une conclusion pour soumettre la fiche."),
    ).toBeVisible();
    expect(screen.getByRole("radio", { name: "Satisfaisant" })).toHaveFocus();
    expect(called).toBe(false);
  });

  it("affiche le refus 422 du serveur (pièce manquante)", async () => {
    server.use(
      http.patch(`${API_URL}/api/v1/test-sheets/${FICHE}/`, () => HttpResponse.json(aFiche())),
      http.post(`${API_URL}/api/v1/test-sheets/${FICHE}/submit/`, () =>
        HttpResponse.json(
          { detail: "Déposez une pièce justificative ou justifiez son absence.", errors: {} },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("radio", { name: "Satisfaisant" }));
    await user.click(screen.getByRole("button", { name: "Soumettre la fiche" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Déposez une pièce");
  });

  it("liste la pièce avec l'empreinte abrégée et télécharge via downloadEvidence", async () => {
    const spy = vi.spyOn(download, "downloadEvidence").mockResolvedValue(undefined);
    const user = userEvent.setup();
    setup({ pieces: [aPiece()] });
    expect(await screen.findByText("Facture 12")).toBeVisible();
    expect(screen.getByText("abcdef012345…")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Télécharger" }));
    expect(spy).toHaveBeenCalledWith("44444444-4444-4444-8444-444444444444", "facture.pdf");
  });

  it("annonce l'erreur d'intégrité (409) au téléchargement", async () => {
    vi.spyOn(download, "downloadEvidence").mockRejectedValue(
      new ApiError(409, "Intégrité de la pièce non garantie : l'empreinte ne correspond pas."),
    );
    const user = userEvent.setup();
    setup({ pieces: [aPiece()] });
    await user.click(await screen.findByRole("button", { name: "Télécharger" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Intégrité de la pièce");
  });

  it("renomme une pièce via un dialogue (pas de window.prompt)", async () => {
    const prompt = vi.spyOn(window, "prompt");
    let body: unknown;
    server.use(
      http.patch(`${API_URL}/api/v1/evidence/:id/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aPiece({ libelle: "Facture 13" }));
      }),
    );
    const user = userEvent.setup();
    setup({ pieces: [aPiece({ actions_possibles: ["TELECHARGER", "MODIFIER"] })] });
    await user.click(await screen.findByRole("button", { name: "Renommer" }));
    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByLabelText("Nouveau libellé");
    await user.clear(input);
    await user.type(input, "Facture 13");
    await user.click(within(dialog).getByRole("button", { name: "Renommer" }));
    await waitFor(() => expect(body).toEqual({ libelle: "Facture 13" }));
    expect(prompt).not.toHaveBeenCalled();
  });

  it("fiche validée : ni dépôt ni retrait de pièce, formulaire en lecture seule", async () => {
    setup({
      fiche: aFiche({ statut: "VALIDE", conclusion: "SATISFAISANT", actions_possibles: [] }),
      pieces: [aPiece()],
    });
    expect(await screen.findByText("Facture 12")).toBeVisible();
    expect(screen.queryByLabelText("Fichier à déposer")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retirer" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Enregistrer le brouillon" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Travaux réalisés")).toBeDisabled();
  });

  it("ne propose « Valider la fiche » que si le serveur l'autorise", async () => {
    const { unmount } = setup({
      fiche: aFiche({ statut: "SOUMIS", actions_possibles: ["RENVOYER"] }),
    });
    expect(await screen.findByRole("button", { name: "Renvoyer" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Valider la fiche" })).not.toBeInTheDocument();
    unmount();
    setup({ fiche: aFiche({ statut: "SOUMIS", actions_possibles: ["VALIDER", "RENVOYER"] }) });
    expect(await screen.findByRole("button", { name: "Valider la fiche" })).toBeVisible();
  });

  it("la validation exige la case « Je confirme » (jamais pré-cochée)", async () => {
    const user = userEvent.setup();
    setup({ fiche: aFiche({ statut: "SOUMIS", actions_possibles: ["VALIDER"] }) });
    await user.click(await screen.findByRole("button", { name: "Valider la fiche" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByRole("checkbox")).not.toBeChecked();
    expect(within(dialog).getByRole("button", { name: "Valider la fiche" })).toBeDisabled();
  });

  it("le renvoi exige un motif", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/test-sheets/${FICHE}/return/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aFiche({ statut: "RENVOYE" }));
      }),
    );
    const user = userEvent.setup();
    setup({ fiche: aFiche({ statut: "SOUMIS", actions_possibles: ["RENVOYER"] }) });
    await user.click(await screen.findByRole("button", { name: "Renvoyer" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Renvoyer" }));
    expect(await within(dialog).findByRole("alert")).toBeVisible();
    expect(body).toBeUndefined();
    await user.type(within(dialog).getByRole("textbox"), "Pièces illisibles");
    await user.click(within(dialog).getByRole("button", { name: "Renvoyer" }));
    await waitFor(() => expect(body).toEqual({ motif: "Pièces illisibles" }));
  });

  it("affiche le motif de renvoi en alerte et le journal", async () => {
    setup({
      fiche: aFiche({
        statut: "RENVOYE",
        motif_renvoi: "Pièces illisibles",
        evenements: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            type: "RENVOYEE",
            par: USER,
            le: "2026-05-05T10:00:00Z",
            motif: "Pièces illisibles",
            statut_avant: "SOUMIS",
            statut_apres: "RENVOYE",
          },
        ],
      }),
    });
    expect(await screen.findByText("Motif du renvoi : Pièces illisibles")).toBeVisible();
    expect(screen.getByText("Fiche renvoyée", { selector: "strong" })).toBeVisible();
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup({ pieces: [aPiece()] });
    await screen.findByText("Facture 12");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
