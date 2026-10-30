import { configure, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { page, renderReferentiel } from "./testUtils";

const s = fr.refStructure;

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

const PROCESS = {
  id: "p1",
  code: "FEP",
  libelle: "Fournir l'eau potable",
  famille: "REALISATION",
  ordre: 1,
  directions_detail: [],
};
const op = (id: string, libelle: string) => ({
  id,
  processus: "p1",
  parent: "o1",
  nature: "OPERATION",
  libelle,
  description: "",
  ordre: 0,
});
const TREE = [
  {
    id: "o1",
    libelle: "Captage",
    description: "",
    ordre: 0,
    operations: [op("o2", "Pompage"), op("o3", "Stockage")],
  },
];

function serve(tree: object[]) {
  server.use(
    http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json(page([PROCESS]))),
    http.get(`${API_URL}/api/v1/auditable-objects/tree/`, () => HttpResponse.json(tree)),
  );
}

describe("AuditableObjectsPage", () => {
  it("asks to choose a process first", async () => {
    serve([]);
    renderReferentiel("/referentiel/objets-auditables", "RAI");
    expect(await screen.findByText(s.noProcessSelectedTitle)).toBeInTheDocument();
  });

  it("renders a domain with two operations in titled nested lists", async () => {
    serve(TREE);
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    expect(await screen.findByRole("heading", { level: 4, name: "Captage" })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Captage" });
    expect(list.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByText("Pompage")).toBeInTheDocument();
  });

  it("offers an empty state with an add action when the process has no domain", async () => {
    serve([]);
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    expect(await screen.findByText(s.noDomainTitle)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: s.addDomain })).toBeInTheDocument();
  });

  it("shows no write control to an ADMIN (RAI only)", async () => {
    serve(TREE);
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "ADMIN");
    await screen.findByText("Pompage");
    expect(screen.queryByRole("button", { name: s.addDomain })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Modifier/ })).not.toBeInTheDocument();
  });

  it("adds an operation under a domain", async () => {
    serve(TREE);
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/auditable-objects/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(op("o4", "Traitement"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    await user.click(await screen.findByRole("button", { name: /Ajouter une opération/ }));
    await user.type(await screen.findByLabelText(fr.referentiel.libelle), "Traitement");
    await user.click(screen.getByRole("button", { name: fr.common.save }));
    await vi.waitFor(() =>
      expect(body).toEqual({
        libelle: "Traitement",
        description: "",
        ordre: 0,
        processus: "p1",
        nature: "OPERATION",
        parent: "o1",
      }),
    );
  });

  it("moves focus between tree actions with the arrow keys", async () => {
    serve(TREE);
    const user = userEvent.setup();
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    const first = await screen.findByRole("button", { name: "Modifier Captage" });
    first.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "Supprimer Captage" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(first).toHaveFocus();
  });

  it("names the selected process above the tree", async () => {
    serve(TREE);
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "AUDITEUR");
    expect(
      await screen.findByRole("heading", { level: 3, name: "FEP - Fournir l'eau potable" }),
    ).toBeInTheDocument();
  });

  it("shows an error when the process list fails to load", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderReferentiel("/referentiel/objets-auditables", "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent(s.loadError);
  });

  it("shows the 422 detail when deleting an operation", async () => {
    serve(TREE);
    const detail = "Cette opération porte des risques.";
    server.use(
      http.delete(`${API_URL}/api/v1/auditable-objects/o2/`, () =>
        HttpResponse.json({ detail }, { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    await user.click(await screen.findByRole("button", { name: "Supprimer Pompage" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: fr.common.delete }));
    expect(await within(dialog).findByText(detail)).toBeInTheDocument();
  });

  it("has no accessibility violation with a dialog open", async () => {
    serve(TREE);
    const user = userEvent.setup();
    renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    await user.click(await screen.findByRole("button", { name: s.addDomain }));
    await screen.findByRole("dialog");
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("has no accessibility violation", async () => {
    serve(TREE);
    const { container } = renderReferentiel("/referentiel/objets-auditables?processus=p1", "RAI");
    await screen.findByText("Pompage");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
