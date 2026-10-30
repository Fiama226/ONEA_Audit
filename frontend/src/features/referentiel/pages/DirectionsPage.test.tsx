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

const DEX = { id: "d1", code: "DEX", libelle: "Exploitation", type: "DIRECTION", parent: null };
const DEP = {
  id: "d2",
  code: "DEP-1",
  libelle: "Production",
  type: "DEPARTEMENT",
  parent: "d1",
};

function serve(results: object[]) {
  server.use(http.get(`${API_URL}/api/v1/directions/`, () => HttpResponse.json(page(results))));
}

describe("DirectionsPage", () => {
  it("lists departments under their direction", async () => {
    serve([DEP, DEX]);
    renderReferentiel("/referentiel/directions", "RAI");
    await screen.findByText("Exploitation");
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]!).getByText("DEX")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("DEP-1")).toBeInTheDocument();
  });

  it("hides write controls from an AUDITEUR", async () => {
    serve([DEX]);
    renderReferentiel("/referentiel/directions", "AUDITEUR");
    await screen.findByText("Exploitation");
    expect(screen.queryByRole("button", { name: s.addEntity })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Modifier/ })).not.toBeInTheDocument();
  });

  it("refuses a department without a parent direction", async () => {
    serve([DEX]);
    let called = false;
    server.use(
      http.post(`${API_URL}/api/v1/directions/`, () => {
        called = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "ADMIN");
    await user.click(await screen.findByRole("button", { name: s.addEntity }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText(fr.referentiel.type), "DEPARTEMENT");
    await user.type(within(dialog).getByLabelText(fr.referentiel.code), "DEP-2");
    await user.type(within(dialog).getByLabelText(fr.referentiel.libelle), "Maintenance");
    await user.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByText(s.errParentRequired)).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("creates a direction", async () => {
    serve([]);
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/directions/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(DEX, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "RAI");
    await user.click(await screen.findByRole("button", { name: s.addEntity }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(fr.referentiel.code), "DEX");
    await user.type(within(dialog).getByLabelText(fr.referentiel.libelle), "Exploitation");
    await user.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await vi.waitFor(() =>
      expect(body).toEqual({
        code: "DEX",
        libelle: "Exploitation",
        type: "DIRECTION",
        parent: null,
      }),
    );
  });

  it("loads every page and warns when the list is incomplete", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/directions/`, ({ request }) => {
        const n = Number(new URL(request.url).searchParams.get("page"));
        return HttpResponse.json({
          count: 3,
          next: n === 1 ? "http://x/?page=2" : null,
          previous: null,
          results: n === 1 ? [DEX] : [DEP],
        });
      }),
    );
    renderReferentiel("/referentiel/directions", "RAI");
    expect(await screen.findByText("Production")).toBeInTheDocument();
    expect(screen.getByText("Exploitation")).toBeInTheDocument();
    expect(screen.getByText(/Liste incomplète/)).toBeInTheDocument();
  });

  it("tells screen readers which direction a department belongs to", async () => {
    serve([DEX, { ...DEP, parent_code: "DEX" }]);
    renderReferentiel("/referentiel/directions", "AUDITEUR");
    expect(await screen.findByText(/Rattaché à DEX/)).toBeInTheDocument();
  });

  it("PATCHes an edited entity", async () => {
    serve([DEX]);
    let body: unknown;
    server.use(
      http.patch(`${API_URL}/api/v1/directions/d1/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(DEX);
      }),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "RAI");
    await user.click(await screen.findByRole("button", { name: `${s.editEntity} DEX` }));
    const dialog = await screen.findByRole("dialog");
    const libelle = within(dialog).getByLabelText(fr.referentiel.libelle);
    await user.clear(libelle);
    await user.type(libelle, "Exploitation eau");
    await user.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await vi.waitFor(() =>
      expect(body).toEqual({
        code: "DEX",
        libelle: "Exploitation eau",
        type: "DIRECTION",
        parent: null,
      }),
    );
  });

  it("shows the 422 detail when deleting a referenced direction", async () => {
    serve([DEX]);
    const detail = "Cette direction est encore rattachée à des processus.";
    server.use(
      http.delete(`${API_URL}/api/v1/directions/d1/`, () =>
        HttpResponse.json({ detail }, { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "RAI");
    await user.click(await screen.findByRole("button", { name: `${s.deleteEntity} DEX` }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: fr.common.delete }));
    expect(await within(dialog).findByText(detail)).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("moves focus to the page heading after a successful deletion", async () => {
    serve([DEX]);
    server.use(
      http.delete(
        `${API_URL}/api/v1/directions/d1/`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "RAI");
    await user.click(await screen.findByRole("button", { name: `${s.deleteEntity} DEX` }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: fr.common.delete }));
    await vi.waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: "Directions" })).toHaveFocus(),
    );
  });

  it("has no accessibility violation with the form dialog open", async () => {
    serve([DEX]);
    const user = userEvent.setup();
    renderReferentiel("/referentiel/directions", "RAI");
    await user.click(await screen.findByRole("button", { name: s.addEntity }));
    await screen.findByRole("dialog");
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("has no accessibility violation", async () => {
    serve([DEX, DEP]);
    const { container } = renderReferentiel("/referentiel/directions", "RAI");
    await screen.findByText("Exploitation");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
