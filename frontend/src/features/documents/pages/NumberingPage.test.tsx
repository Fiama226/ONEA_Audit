import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aFormat, aType } from "./adminFixtures";
import { NumberingPage } from "./NumberingPage";

const FORMATS = `${API_URL}/api/v1/numbering-formats/`;

function renderPage(role: Role = "ADMIN") {
  server.use(
    http.get(FORMATS, () => HttpResponse.json([aFormat()])),
    http.get(`${API_URL}/api/v1/document-types/`, () => HttpResponse.json([aType()])),
  );
  return renderRoutes([{ path: "*", element: <NumberingPage /> }], role);
}

async function openEditor() {
  await userEvent.click(
    await screen.findByRole("button", { name: "Modifier le format de Ordre de mission" }),
  );
  return screen.findByRole("dialog");
}

describe("NumberingPage", () => {
  it("lists formats with the help text", async () => {
    const { container } = renderPage();
    expect(await screen.findByText("Par mission")).toBeInTheDocument();
    expect(screen.getByText("MI-2026-001/OM-01")).toBeInTheDocument();
    expect(
      screen.getByText(/Champs permis : \{mission\}, \{annee\}, \{code\}, \{sequence\}/),
    ).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("shows the server preview error on the model field while typing", async () => {
    server.use(
      http.post(`${FORMATS}preview/`, async ({ request }) => {
        const body = (await request.json()) as { modele: string };
        return HttpResponse.json({
          numero: null,
          errors: {
            modele: [
              `Champ inconnu : {seq}. Champs permis : {mission}, {annee}, {code}, {sequence}.`,
            ],
          },
          echo: body.modele,
        });
      }),
    );
    renderPage();
    const dialog = await openEditor();
    const input = screen.getByLabelText("Modèle");
    await userEvent.clear(input);
    await userEvent.type(input, "{{mission}/{{code}-{{seq}", {});
    expect(
      await screen.findByText(/Champ inconnu : \{seq\}/, undefined, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toBeTruthy();
    expect(dialog).toBeInTheDocument();
    expect(
      (await axe(dialog, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("saves via PATCH and maps a 422 to the field with focus", async () => {
    let patched: unknown = null;
    server.use(
      http.post(`${FORMATS}preview/`, () => HttpResponse.json({ numero: "X-01", errors: {} })),
      http.patch(`${FORMATS}ORDRE_MISSION/`, async ({ request }) => {
        patched = await request.json();
        return HttpResponse.json(
          { detail: "Format invalide.", errors: { abreviation: ["Abréviation déjà utilisée."] } },
          { status: 422 },
        );
      }),
    );
    renderPage();
    await openEditor();
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le format" }));
    expect(await screen.findByText("Abréviation déjà utilisée.")).toBeInTheDocument();
    expect(screen.getByLabelText("Abréviation")).toHaveFocus();
    expect(patched).toEqual({
      modele: "{mission}/{code}-{sequence}",
      portee: "MISSION",
      abreviation: "OM",
    });
  });

  it("maps 403 to a visible message and closes on success", async () => {
    let status = 403;
    server.use(
      http.post(`${FORMATS}preview/`, () => HttpResponse.json({ numero: "X-01", errors: {} })),
      http.patch(`${FORMATS}ORDRE_MISSION/`, () =>
        status === 403
          ? HttpResponse.json({ detail: "Accès refusé." }, { status: 403 })
          : HttpResponse.json(aFormat()),
      ),
    );
    renderPage();
    await openEditor();
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le format" }));
    expect(await screen.findByText("Accès refusé.")).toBeInTheDocument();
    status = 200;
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le format" }));
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("validates lengths client-side", async () => {
    renderPage();
    await openEditor();
    await userEvent.clear(screen.getByLabelText("Abréviation"));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le format" }));
    expect(await screen.findByText("Saisissez une abréviation.")).toBeInTheDocument();
    expect(screen.getByLabelText("Modèle")).toHaveAttribute("maxlength", "80");
  });

  it("gives RAI no edit button", async () => {
    renderPage("RAI");
    await screen.findByText("Par mission");
    expect(screen.queryByRole("button", { name: /Modifier/ })).not.toBeInTheDocument();
  });

  it("shows an error rather than an empty table when loading fails", async () => {
    server.use(http.get(FORMATS, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    server.use(http.get(`${API_URL}/api/v1/document-types/`, () => HttpResponse.json([aType()])));
    renderRoutes([{ path: "*", element: <NumberingPage /> }], "ADMIN");
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
