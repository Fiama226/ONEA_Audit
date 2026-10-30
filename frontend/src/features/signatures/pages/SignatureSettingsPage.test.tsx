import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import type { ParametreSignature } from "../adminApi";
import { SignatureSettingsPage } from "./SignatureSettingsPage";

const URL = `${API_URL}/api/v1/signature-settings/`;

function aSetting(overrides: Partial<ParametreSignature> = {}): ParametreSignature {
  return {
    type_document: "VALIDATION_RAPPORT",
    type_libelle: "Validation du rapport",
    mode: "CONFIRMATION",
    mode_libelle: "Confirmation horodatée",
    modes_disponibles: [
      { mode: "CONFIRMATION", libelle: "Confirmation horodatée" },
      { mode: "CONFIRMATION_ET_SIGNATURE", libelle: "Confirmation et signature" },
    ],
    modifie_le: "2026-03-05T09:00:00Z",
    modifie_par: { id: 2, nom_complet: "Awa Ouedraogo" },
    ...overrides,
  };
}

function renderPage(role: Role = "ADMIN") {
  return renderRoutes([{ path: "*", element: <SignatureSettingsPage /> }], role);
}

describe("SignatureSettingsPage", () => {
  it("lets the admin change a mode after confirmation", async () => {
    let body: unknown = null;
    server.use(
      http.get(URL, () => HttpResponse.json([aSetting()])),
      http.patch(`${URL}VALIDATION_RAPPORT/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aSetting());
      }),
    );
    const { container } = renderPage();
    const select = await screen.findByRole("combobox", {
      name: "Mode de signature de Validation du rapport",
    });
    expect(screen.getByText("Awa Ouedraogo")).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
    expect(screen.getByRole("option", { name: "Signature électronique (PAdES)" })).toBeDisabled();
    expect(
      screen.getByText("Disponible après l'installation de la signature électronique (lot 7 bis)."),
    ).toBeInTheDocument();

    await userEvent.selectOptions(select, "CONFIRMATION_ET_SIGNATURE");
    expect(body).toBeNull();
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "Le nouveau mode s'applique aux prochaines validations ; les documents déjà validés ne changent pas.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Modifier le mode" }));
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
    expect(body).toEqual({ mode: "CONFIRMATION_ET_SIGNATURE" });
  });

  it("enables electronic modes only when the server offers them", async () => {
    server.use(
      http.get(URL, () =>
        HttpResponse.json([
          aSetting({
            modes_disponibles: [
              { mode: "CONFIRMATION", libelle: "Confirmation horodatée" },
              { mode: "SIGNATURE_ELECTRONIQUE", libelle: "Signature électronique (PAdES)" },
              { mode: "CONFIRMATION_ET_SIGNATURE", libelle: "Confirmation et signature" },
            ],
          }),
        ]),
      ),
    );
    renderPage();
    expect(
      await screen.findByRole("option", { name: "Signature électronique (PAdES)" }),
    ).toBeEnabled();
    expect(screen.queryByText(/lot 7 bis/)).not.toBeInTheDocument();
  });

  it("is read-only for the RAI", async () => {
    server.use(http.get(URL, () => HttpResponse.json([aSetting()])));
    renderPage("RAI");
    expect(await screen.findByText("Validation du rapport")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("Confirmation horodatée")).toBeInTheDocument();
    expect(screen.getByText(/Lecture seule/)).toBeInTheDocument();
  });

  it("shows the server 422 and keeps the dialog open", async () => {
    server.use(
      http.get(URL, () => HttpResponse.json([aSetting()])),
      http.patch(`${URL}VALIDATION_RAPPORT/`, () =>
        HttpResponse.json(
          {
            detail: "Mode refusé.",
            errors: { mode: ["Aucun signataire n'est configuré."] },
          },
          { status: 422 },
        ),
      ),
    );
    renderPage();
    await userEvent.selectOptions(await screen.findByRole("combobox"), "CONFIRMATION_ET_SIGNATURE");
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Modifier le mode" }));
    expect(
      await within(dialog).findByText("Aucun signataire n'est configuré."),
    ).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("shows an error, not an empty table, when loading fails", async () => {
    server.use(http.get(URL, () => HttpResponse.json({ detail: "Erreur" }, { status: 500 })));
    renderPage();
    expect(
      await screen.findByText("Impossible de charger les modes de signature."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
