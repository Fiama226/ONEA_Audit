import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aTemplate, aType, TYPE_CODE } from "./adminFixtures";
import { TemplateDetailPage } from "./TemplateDetailPage";

const TYPES = `${API_URL}/api/v1/document-types/`;
const TEMPLATES = `${API_URL}/api/v1/templates/`;

function page(results = [aTemplate(), aTemplate({ id: "g2", version: 2, statut: "ACTIF" })]) {
  server.use(
    http.get(TYPES, () => HttpResponse.json([aType()])),
    http.get(TEMPLATES, () =>
      HttpResponse.json({ count: results.length, next: null, previous: null, results }),
    ),
  );
}

function renderPage(role: Role = "ADMIN", code = TYPE_CODE) {
  return renderRoutes(
    [{ path: "/administration/documents/:type", element: <TemplateDetailPage /> }],
    role,
    { path: `/administration/documents/${code}` },
  );
}

const docx = (name = "gabarit.docx", size = 100) =>
  new File([new Uint8Array(size)], name, {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });

describe("TemplateDetailPage", () => {
  it("lists versions with actions and the contract tree, no axe violation", async () => {
    page();
    const { container } = renderPage();
    const row = await screen.findByRole("row", { name: "v1" });
    expect(within(row).getByText("om-v1.docx")).toBeInTheDocument();
    expect(within(row).getByText("20 Ko")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Activer" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Aperçu PDF" })).toBeInTheDocument();
    const active = screen.getByRole("row", { name: "v2" });
    expect(within(active).queryByRole("button", { name: "Activer" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: /Balises du contrat/ }),
    ).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("copies the tag of a field and of a list", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    page();
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Copier la balise mission.titre" }),
    );
    expect(writeText).toHaveBeenCalledWith("{{ mission.titre }}");
    expect(await screen.findByText("Balise copiée.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copier la balise ordre.equipe" }));
    expect(writeText).toHaveBeenLastCalledWith("{%tr for l in ordre.equipe %}");
  });

  it("gives unique keys and names to the children of two lists", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const list = (nom: string) => ({
      nom,
      type: "liste" as const,
      description: nom,
      enfants: [{ nom: "code", type: "texte" as const, description: "Code", enfants: [] }],
    });
    server.use(
      http.get(TYPES, () =>
        HttpResponse.json([
          aType({
            champs: [
              {
                nom: "mission",
                type: "bloc",
                description: "M",
                enfants: [list("processus"), list("entites")],
              },
            ],
          }),
        ]),
      ),
      http.get(TEMPLATES, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderPage();
    expect(
      await screen.findByRole("button", { name: "Copier la balise mission.processus.code" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Copier la balise mission.entites.code" }),
    ).toBeInTheDocument();
    expect(error.mock.calls.flat().join(" ")).not.toMatch(/same key|unique "key"/);
    error.mockRestore();
  });

  it("cancels an upload in progress: no error, request aborted", async () => {
    let aborted = false;
    page();
    server.use(
      http.post(TEMPLATES, async ({ request }) => {
        request.signal.addEventListener("abort", () => (aborted = true));
        await new Promise((r) => setTimeout(r, 1500));
        return HttpResponse.json(aTemplate({ id: "g3", version: 3 }), { status: 201 });
      }),
    );
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Déposer une nouvelle version" }),
    );
    await userEvent.upload(screen.getByLabelText("Fichier Word (.docx)"), docx());
    await userEvent.click(screen.getByRole("button", { name: "Déposer" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annuler l'envoi" }));
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await vi.waitFor(() => expect(aborted).toBe(true));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("confirms activation, posts activate and the row becomes Actif", async () => {
    let activated = false;
    server.use(
      http.post(`${TEMPLATES}g1/activate/`, () => {
        activated = true;
        return HttpResponse.json(aTemplate({ statut: "ACTIF" }));
      }),
    );
    page();
    server.use(
      http.get(TEMPLATES, () => {
        const results = activated
          ? [aTemplate({ statut: "ACTIF" }), aTemplate({ id: "g2", version: 2, statut: "ARCHIVE" })]
          : [aTemplate(), aTemplate({ id: "g2", version: 2, statut: "ACTIF" })];
        return HttpResponse.json({ count: 2, next: null, previous: null, results });
      }),
    );
    renderPage();
    const row = await screen.findByRole("row", { name: "v1" });
    await userEvent.click(within(row).getByRole("button", { name: "Activer" }));
    expect(
      await screen.findByText(
        /utiliseront la version 1\. Les documents déjà générés ne changent pas\./,
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Activer la version" }));
    expect(
      await within(await screen.findByRole("row", { name: "v1" })).findByText("Actif"),
    ).toBeInTheDocument();
    expect(activated).toBe(true);
  });

  it("shows a 409 activation error in the dialog", async () => {
    page();
    server.use(
      http.post(`${TEMPLATES}g1/activate/`, () =>
        HttpResponse.json({ detail: "Conflit d'activation." }, { status: 409 }),
      ),
    );
    renderPage();
    await userEvent.click(
      within(await screen.findByRole("row", { name: "v1" })).getByRole("button", {
        name: "Activer",
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Activer la version" }));
    expect(await screen.findByText("Conflit d'activation.")).toBeInTheDocument();
  });

  it("uploads FormData with type_document, fichier, commentaire", async () => {
    let sent: Record<string, FormDataEntryValue> = {};
    page();
    server.use(
      http.post(TEMPLATES, async ({ request }) => {
        sent = Object.fromEntries(await request.formData());
        return HttpResponse.json(aTemplate({ id: "g3", version: 3 }), { status: 201 });
      }),
    );
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Déposer une nouvelle version" }),
    );
    await userEvent.upload(screen.getByLabelText("Fichier Word (.docx)"), docx());
    await userEvent.type(screen.getByLabelText("Commentaire (facultatif)"), "Test");
    await userEvent.click(screen.getByRole("button", { name: "Déposer" }));
    await vi.waitFor(() => expect(sent.type_document).toBe(TYPE_CODE));
    // MSW/undici relit le fichier comme un Blob : le nom n'est pas conservé, la taille l'est.
    expect((sent.fichier as Blob).size).toBe(100);
    expect(sent.commentaire).toBe("Test");
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("lists the three server errors on 422 and keeps the dialog open", async () => {
    page();
    server.use(
      http.post(TEMPLATES, () =>
        HttpResponse.json(
          {
            detail: "Le gabarit est invalide.",
            errors: { fichier: ["Erreur A.", "Erreur B.", "Erreur C."] },
          },
          { status: 422 },
        ),
      ),
    );
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Déposer une nouvelle version" }),
    );
    await userEvent.upload(screen.getByLabelText("Fichier Word (.docx)"), docx());
    await userEvent.click(screen.getByRole("button", { name: "Déposer" }));
    const list = await screen.findByRole("list");
    expect(
      within(list)
        .getAllByRole("listitem")
        .map((l) => l.textContent),
    ).toEqual(["Erreur A.", "Erreur B.", "Erreur C."]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Fichier Word (.docx)")).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining("upload-problems"),
    );
  });

  it("refuses .doc and oversized files client-side without sending", async () => {
    let posts = 0;
    page();
    server.use(
      http.post(TEMPLATES, () => {
        posts += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Déposer une nouvelle version" }),
    );
    await userEvent.upload(screen.getByLabelText("Fichier Word (.docx)"), docx("ancien.doc"), {
      applyAccept: false,
    } as never);
    await userEvent.click(screen.getByRole("button", { name: "Déposer" }));
    expect(await screen.findByText(/Les fichiers \.doc ne sont pas acceptés/)).toBeInTheDocument();
    await userEvent.upload(
      screen.getByLabelText("Fichier Word (.docx)"),
      docx("gros.docx", 10 * 1024 * 1024 + 1),
    );
    await userEvent.click(screen.getByRole("button", { name: "Déposer" }));
    expect(await screen.findByText("Le fichier dépasse 10 Mo.")).toBeInTheDocument();
    expect(posts).toBe(0);
  });

  it("shows progress while a preview is produced and reports its failure", async () => {
    page();
    server.use(
      http.get(`${TEMPLATES}g1/preview/`, async () => {
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json({ detail: "Aperçu impossible." }, { status: 422 });
      }),
    );
    renderPage();
    const row = await screen.findByRole("row", { name: "v1" });
    await userEvent.click(within(row).getByRole("button", { name: "Aperçu Word" }));
    expect(await screen.findByText(/Aperçu en cours de préparation/)).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Aperçu PDF" })).toBeDisabled();
    expect(await screen.findByText("Aperçu impossible.")).toBeInTheDocument();
  });

  it("gives RAI no write button", async () => {
    page();
    renderPage("RAI");
    await screen.findByRole("row", { name: "v1" });
    expect(screen.queryByRole("button", { name: "Activer" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Déposer une nouvelle version" }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Télécharger" }).length).toBeGreaterThan(0);
  });

  it("does not request an unknown type's data as valid and says so", async () => {
    page();
    renderPage("ADMIN", "INCONNU");
    expect(
      await screen.findByRole("heading", { level: 1, name: /n'existe pas/ }),
    ).toBeInTheDocument();
  });

  it("shows an error, not an empty history, when loading fails", async () => {
    server.use(
      http.get(TYPES, () => HttpResponse.json([aType()])),
      http.get(TEMPLATES, () => HttpResponse.json({ detail: "x" }, { status: 500 })),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    expect(
      screen.queryByText("Aucune version déposée pour ce type de document."),
    ).not.toBeInTheDocument();
  });
});
