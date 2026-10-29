import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import {
  allSteps,
  aMission,
  missionHandlers,
  MISSION_ID,
  pageOf,
  renderMission,
} from "@/features/missions/testUtils";
import { API_URL } from "@/test/msw";
import { aFramework, aMarcLine, analyseRights } from "../testUtils";
import type { ReferentielAudit } from "../types";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const url = `/missions/${MISSION_ID}/referentiel-audit`;

function render(
  role: Role,
  framework: ReferentielAudit,
  extra: { posts?: unknown[]; snapshot?: boolean } = {},
) {
  return renderMission(url, role, {
    handlers: [
      ...missionHandlers(aMission(), allSteps()),
      http.get(`${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/`, () =>
        HttpResponse.json(framework),
      ),
      http.get(`${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/snapshot/`, () =>
        HttpResponse.json({
          confirmation: {
            id: "55555555-5555-4555-8555-555555555555",
            type_document: "VALIDATION_REFERENTIEL",
            signataire: { id: 1, nom_complet: "Moussa Sawadogo" },
            confirme_le: "2026-03-21T10:00:00Z",
            empreinte: "3f2a000000000000000000000000000000000000000000000000000000009c1b",
          },
          donnees: {
            risques: [{ id: "r1", code: "R-001", libelle: "Fraude" }],
            lignes_marc: [{ id: "l1", risque_id: "r1", controle_existant: "Version figée" }],
            forces_faiblesses: [],
          },
        }),
      ),
      http.post(
        `${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/opinions/`,
        async ({ request }) => {
          extra.posts?.push(await request.json());
          return HttpResponse.json({}, { status: 201 });
        },
      ),
      http.get(`${API_URL}/api/v1/marc-lines/`, () =>
        HttpResponse.json(pageOf([aMarcLine({ controle_existant: "Double signature." })])),
      ),
      http.get(`${API_URL}/api/v1/strengths-weaknesses/`, () => HttpResponse.json(pageOf([]))),
    ],
  });
}

const SOUMIS = aFramework({ statut: "SOUMIS", nb_lignes: 1 });
const DIFFUSE_AUDITE = aFramework({
  statut: "VALIDE",
  mes_droits: analyseRights({ voir_travaux: false, voir_referentiel: true, donner_avis: true }),
});

describe("AuditFrameworkPage", () => {
  it("shows an empty state to an auditee before the framework is broadcast", async () => {
    render("AUDITE", aFramework({ mes_droits: analyseRights() }));
    expect(
      await screen.findByRole("heading", {
        name: "Le référentiel d'audit n'est pas encore diffusé.",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Donner mon avis" })).not.toBeInTheDocument();
  });

  it("shows the submitted status and the read-only matrix, with no opinion button for the lead", async () => {
    render("RAI", SOUMIS);
    expect(await screen.findByText("Soumis au RAI")).toBeInTheDocument();
    expect(await screen.findByText("Double signature.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Donner mon avis" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter un contrôle" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Imprimer" })).toBeInTheDocument();
  });

  it("lets the auditee send remarks and refuses an empty comment", async () => {
    const posts: unknown[] = [];
    const user = userEvent.setup();
    render("AUDITE", { ...DIFFUSE_AUDITE, statut: "SOUMIS" }, { posts });
    await user.click(await screen.findByRole("button", { name: "Donner mon avis" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Avis"), "REMARQUES");
    await user.click(within(dialog).getByRole("button", { name: "Confirmer" }));
    expect(
      await within(dialog).findByText(
        "Le commentaire est obligatoire quand vous émettez des remarques.",
      ),
    ).toBeInTheDocument();
    expect(posts).toEqual([]);
    await user.type(within(dialog).getByLabelText("Commentaire"), "Revoir R-001.");
    await user.click(within(dialog).getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(posts).toEqual([{ avis: "REMARQUES", commentaire: "Revoir R-001." }]),
    );
  });

  it("reads the frozen snapshot once validated", async () => {
    render("RAI", { ...SOUMIS, statut: "VALIDE" });
    expect(await screen.findByText("Version validée le 21/03/2026")).toBeInTheDocument();
    expect(await screen.findByText("Version figée")).toBeInTheDocument();
    expect(screen.queryByText("Double signature.")).not.toBeInTheDocument();
  });

  it("prints the framework without the action buttons", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const user = userEvent.setup();
    render("RAI", SOUMIS);
    await user.click(await screen.findByRole("button", { name: "Imprimer" }));
    expect(print).toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Référentiel d'audit" })).toBeInTheDocument();
    print.mockRestore();
  });

  it("has no axe violation with the opinion dialog open", async () => {
    const user = userEvent.setup();
    const { container } = render("AUDITE", { ...DIFFUSE_AUDITE, statut: "SOUMIS" });
    await user.click(await screen.findByRole("button", { name: "Donner mon avis" }));
    const dialog = await screen.findByRole("dialog");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
  });
});
