import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aDisponible, aDocument, aVersion, OBJET_ID, renderDocuments } from "../testUtils";
import { GenerateDocumentButton } from "./GenerateDocumentButton";

const d = fr.documents;

describe("GenerateDocumentButton", () => {
  it("shows the server reason and disables the button when generation is not allowed", async () => {
    const { container } = renderDocuments(
      <GenerateDocumentButton
        disponible={aDisponible({ peut_generer: false, raison: "L'étape n'est pas terminée." })}
      />,
    );
    const button = screen.getByRole("button", { name: d.generate });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("L'étape n'est pas terminée.");
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("posts the generation request", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/api/v1/documents/generate/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aVersion({ statut: "EN_ATTENTE" }), { status: 202 });
      }),
    );
    renderDocuments(<GenerateDocumentButton disponible={aDisponible()} />);
    await userEvent.click(screen.getByRole("button", { name: d.generate }));
    await screen.findByRole("button", { name: d.generate });
    expect(body).toEqual({ type_document: "ORDRE_MISSION", objet: OBJET_ID });
  });

  it("labels the button « Régénérer » when a document exists", () => {
    renderDocuments(<GenerateDocumentButton disponible={aDisponible({ document: aDocument() })} />);
    expect(screen.getByRole("button", { name: d.regenerate })).toBeEnabled();
  });

  it("displays a 422 as an alert", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/documents/generate/`, () =>
        HttpResponse.json({ detail: "Données incomplètes.", errors: {} }, { status: 422 }),
      ),
    );
    renderDocuments(<GenerateDocumentButton disponible={aDisponible()} />);
    await userEvent.click(screen.getByRole("button", { name: d.generate }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Données incomplètes.");
  });
});
