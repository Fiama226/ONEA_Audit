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
  configure({ asyncUtilTimeout: 4000 });
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

  it("has no accessibility violation", async () => {
    serve([DEX, DEP]);
    const { container } = renderReferentiel("/referentiel/directions", "RAI");
    await screen.findByText("Exploitation");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
