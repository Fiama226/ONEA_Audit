import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aType } from "./adminFixtures";
import { TemplatesPage } from "./TemplatesPage";

const TYPES = `${API_URL}/api/v1/document-types/`;

function renderPage() {
  return renderRoutes([{ path: "*", element: <TemplatesPage /> }], "ADMIN");
}

describe("TemplatesPage", () => {
  it("lists the active template, provisional badge and banner", async () => {
    server.use(http.get(TYPES, () => HttpResponse.json([aType()])));
    const { container } = renderPage();
    const row = await screen.findByRole("row", { name: /Ordre de mission/ });
    expect(within(row).getByText("v2")).toBeInTheDocument();
    expect(within(row).getByText("Provisoire")).toBeInTheDocument();
    expect(within(row).getByText("05/03/2026")).toBeInTheDocument();
    expect(within(row).getByText("v1")).toBeInTheDocument();
    expect(
      screen.getByText(
        "1 document utilise un gabarit provisoire en attente du modèle officiel ONEA.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("shows an error with retry instead of an empty table", async () => {
    server.use(http.get(TYPES, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows no banner without provisional template", async () => {
    server.use(
      http.get(TYPES, () =>
        HttpResponse.json([
          aType({
            gabarit_actif: {
              id: "g",
              version: 3,
              statut: "ACTIF",
              provisoire: false,
              active_le: null,
            },
          }),
        ]),
      ),
    );
    renderPage();
    await screen.findByText("v3");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
