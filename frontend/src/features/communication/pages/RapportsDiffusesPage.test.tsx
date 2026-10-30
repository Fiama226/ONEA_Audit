import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aRapportDiffuse, pageOf } from "../testUtils";
import type { RapportDiffuse } from "../types";
import { RapportsDiffusesPage } from "./RapportsDiffusesPage";

const t = fr.rapportFinal;

function renderList(results: RapportDiffuse[], role: Role = "DG") {
  server.use(http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json(pageOf(results))));
  return renderRoutes([{ path: "/rapports", element: <RapportsDiffusesPage /> }], role, {
    path: "/rapports",
  });
}

describe("RapportsDiffusesPage", () => {
  it("affiche le message du DG quand aucun rapport n'a été diffusé", async () => {
    renderList([]);
    expect(await screen.findByText("Aucun rapport n'a encore été diffusé.")).toBeInTheDocument();
  });

  it("liste les rapports sans lien vers la mission pour le DG", async () => {
    const { container } = renderList([
      aRapportDiffuse({ mon_accuse_reception: "2026-10-30T08:00:00Z" }),
    ]);
    const link = await screen.findByRole("link", { name: /MI-2026-001/ });
    expect(link).toHaveAttribute("href", "/rapports/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa");
    expect(container.querySelector('a[href*="/missions"]')).toBeNull();
    const row = screen.getByRole("row", { name: /MI-2026-001/ });
    expect(within(row).getByText("RA-2026-001")).toBeInTheDocument();
    expect(within(row).getByText("29/10/2026")).toBeInTheDocument();
    expect(within(row).getByText("Perfectible")).toBeInTheDocument();
    expect(within(row).getByText("Accusé le 30/10/2026")).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("filtre par année de diffusion", async () => {
    const user = userEvent.setup();
    renderList(
      [
        aRapportDiffuse({
          id: "a1",
          mission_reference: "MI-2025-007",
          diffuse_le: "2025-03-01T09:00:00Z",
        }),
        aRapportDiffuse({ id: "a2", mission_reference: "MI-2026-001" }),
      ],
      "RAI",
    );
    await screen.findByRole("link", { name: /MI-2025-007/ });
    await user.selectOptions(screen.getByLabelText(t.distYear), "2026");
    expect(screen.queryByRole("link", { name: /MI-2025-007/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /MI-2026-001/ })).toBeInTheDocument();
  });

  it("n'affiche pas une erreur de chargement comme une liste vide", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoutes([{ path: "/rapports", element: <RapportsDiffusesPage /> }], "DG", {
      path: "/rapports",
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(t.distLoadError);
    expect(screen.queryByText(t.distEmptyDg)).not.toBeInTheDocument();
  });
});
