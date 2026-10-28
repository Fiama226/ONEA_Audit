import { configure, screen, waitFor } from "@testing-library/react";
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
  configure({ asyncUtilTimeout: 4000 });
});

const DIRECTION = {
  id: "d1",
  code: "DEX",
  libelle: "Exploitation",
  type: "DIRECTION",
  parent: null,
};
const PROCESS = {
  id: "p1",
  code: "FEP",
  libelle: "Fournir l'eau potable",
  famille: "REALISATION",
  ordre: 4,
  directions_detail: [{ id: "d1", code: "DEX", libelle: "Exploitation" }],
};

function serveBase() {
  server.use(
    http.get(`${API_URL}/api/v1/directions/`, () => HttpResponse.json(page([DIRECTION]))),
    http.get(`${API_URL}/api/v1/processes/p1/`, () => HttpResponse.json(PROCESS)),
  );
}

describe("ProcessFormPage", () => {
  it("creates a process with the expected payload", async () => {
    serveBase();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/processes/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...PROCESS }, { status: 201 });
      }),
      http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json(page([]))),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/processus/nouveau", "RAI");
    await user.click(await screen.findByRole("checkbox", { name: /DEX/ }));
    await user.type(screen.getByLabelText(fr.referentiel.code), "FEP");
    await user.type(screen.getByLabelText(fr.referentiel.libelle), "Fournir l'eau potable");
    await user.selectOptions(screen.getByLabelText(fr.referentiel.famille), "REALISATION");
    await user.clear(screen.getByLabelText(fr.referentiel.ordre));
    await user.type(screen.getByLabelText(fr.referentiel.ordre), "4");
    await user.click(screen.getByRole("button", { name: fr.common.save }));
    await waitFor(() =>
      expect(body).toEqual({
        code: "FEP",
        libelle: "Fournir l'eau potable",
        famille: "REALISATION",
        ordre: 4,
        directions: ["d1"],
      }),
    );
  });

  it("blocks an invalid code client-side", async () => {
    serveBase();
    let called = false;
    server.use(
      http.post(`${API_URL}/api/v1/processes/`, () => {
        called = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/processus/nouveau", "RAI");
    const code = await screen.findByLabelText(fr.referentiel.code);
    await user.type(code, "ést");
    await user.type(screen.getByLabelText(fr.referentiel.libelle), "X");
    await user.click(screen.getByRole("button", { name: fr.common.save }));
    expect(
      await screen.findByText(s.errCodeProcess, { selector: "p[id$='-error']" }),
    ).toBeInTheDocument();
    expect(code).toHaveAttribute("aria-invalid", "true");
    expect(called).toBe(false);
  });

  it("maps server field errors onto the fields", async () => {
    serveBase();
    server.use(
      http.post(`${API_URL}/api/v1/processes/`, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { code: ["Ce code existe déjà."] } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/processus/nouveau", "RAI");
    await user.type(await screen.findByLabelText(fr.referentiel.code), "FEP");
    await user.type(screen.getByLabelText(fr.referentiel.libelle), "Eau");
    await user.selectOptions(screen.getByLabelText(fr.referentiel.famille), "SUPPORT");
    await user.click(screen.getByRole("button", { name: fr.common.save }));
    expect(await screen.findByText("Ce code existe déjà.")).toBeInTheDocument();
    expect(screen.getByLabelText(fr.referentiel.code)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows the 422 detail in the delete confirmation without closing it", async () => {
    serveBase();
    const detail = "Ce processus porte des risques et ne peut pas être supprimé.";
    server.use(
      http.delete(`${API_URL}/api/v1/processes/p1/`, () =>
        HttpResponse.json({ detail }, { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    renderReferentiel("/referentiel/processus/p1", "RAI");
    expect(await screen.findByDisplayValue("Fournir l'eau potable")).toBeInTheDocument();
    expect(screen.getByLabelText(fr.referentiel.code)).toBeDisabled();
    await user.click(screen.getByRole("button", { name: s.deleteProcess }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(await screen.findByRole("button", { name: fr.common.delete }));
    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(dialog).toBeInTheDocument();
  });

  it("is read-only for an AUDITEUR", async () => {
    serveBase();
    renderReferentiel("/referentiel/processus/p1", "AUDITEUR");
    expect(await screen.findByDisplayValue("Fournir l'eau potable")).toBeDisabled();
    expect(screen.queryByRole("button", { name: fr.common.save })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: s.deleteProcess })).not.toBeInTheDocument();
  });

  it("has no accessibility violation", async () => {
    serveBase();
    const { container } = renderReferentiel("/referentiel/processus/p1", "RAI");
    await screen.findByDisplayValue("Fournir l'eau potable");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
