import { configure, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aLine, aPlan, LINE_ID, page, PLAN_ID, renderPlan } from "../testUtils";

const s = fr.programmationLignes;

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 4000 });
});

const PROCESS = {
  id: "p1",
  code: "FEP",
  libelle: "Approvisionnement",
  famille: "SUPPORT",
  ordre: 1,
  directions_detail: [],
};
const PROCESS2 = { ...PROCESS, id: "p2", code: "RHU", libelle: "Ressources humaines" };
const TREE = [
  {
    id: "dom1",
    libelle: "Achats",
    description: "",
    ordre: 1,
    operations: [
      { id: "op1", processus: "p1", parent: "dom1", nature: "OPERATION", libelle: "Marchés" },
    ],
  },
];
const DIRECTIONS = [
  {
    id: "d1",
    code: "DAF",
    libelle: "Direction administrative",
    type: "DIRECTION",
    parent: null,
    parent_code: null,
  },
  {
    id: "d2",
    code: "SCP",
    libelle: "Service comptable",
    type: "DEPARTEMENT",
    parent: "d1",
    parent_code: "DAF",
  },
];

function serve(plan = aPlan()) {
  server.use(
    http.get(`${API_URL}/api/v1/processes/`, () => HttpResponse.json(page([PROCESS, PROCESS2]))),
    http.get(`${API_URL}/api/v1/directions/`, () => HttpResponse.json(page(DIRECTIONS))),
    http.get(`${API_URL}/api/v1/auditable-objects/tree/`, () => HttpResponse.json(TREE)),
    http.get(`${API_URL}/api/v1/audit-plans/${PLAN_ID}/`, () => HttpResponse.json(plan)),
    http.get(`${API_URL}/api/v1/audit-plans/`, () => HttpResponse.json(page([plan]))),
  );
}

const NEW_PATH = `/programme-annuel/${PLAN_ID}/nouvelle-ligne`;
const EDIT_PATH = `/programme-annuel/lignes/${LINE_ID}`;

async function fillBase(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("option", { name: /FEP - Approvisionnement/ });
  await user.type(screen.getByLabelText(s.lineTitle), "Audit de la gestion des achats");
  await user.selectOptions(screen.getByLabelText(fr.programmation.process), "p1");
  await user.click(await screen.findByLabelText(/DAF - Direction administrative/));
  await user.type(screen.getByLabelText(fr.programmation.plannedStart), "2026-03-02");
  await user.type(screen.getByLabelText(fr.programmation.plannedEnd), "2026-04-30");
}

describe("AuditPlanLineFormPage", () => {
  it("creates a line with the expected payload and returns to the plan", async () => {
    serve();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aLine(), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const { router } = renderPlan(NEW_PATH, "RAI");
    await fillBase(user);
    await user.type(screen.getByLabelText(fr.programmation.plannedDays), "20");
    await user.type(screen.getByLabelText(fr.programmation.justification), "Risque élevé");
    await user.click(screen.getByRole("button", { name: s.save }));
    await waitFor(() =>
      expect(body).toEqual({
        programme: PLAN_ID,
        titre: "Audit de la gestion des achats",
        type: "ASSURANCE",
        processus: "p1",
        objet_auditable: null,
        entites: ["d1"],
        debut_prevu: "2026-03-02",
        fin_prevue: "2026-04-30",
        charge_prevue_jours: "20.0",
        justification: "Risque élevé",
      }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/programme-annuel/${PLAN_ID}`),
    );
    expect(router.state.location.state).toEqual({ flash: s.saved });
  });

  it("blocks an end date before the start date on the client", async () => {
    serve();
    const post = vi.fn();
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, () => {
        post();
        return HttpResponse.json(aLine());
      }),
    );
    const user = userEvent.setup();
    renderPlan(NEW_PATH, "RAI");
    await fillBase(user);
    await user.clear(screen.getByLabelText(fr.programmation.plannedEnd));
    await user.type(screen.getByLabelText(fr.programmation.plannedEnd), "2026-02-01");
    await user.click(screen.getByRole("button", { name: s.save }));
    expect(await screen.findByText(s.errEndBeforeStart)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("blocks a start date outside the plan year on the client", async () => {
    serve();
    const post = vi.fn();
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, () => {
        post();
        return HttpResponse.json(aLine());
      }),
    );
    const user = userEvent.setup();
    renderPlan(NEW_PATH, "RAI");
    await fillBase(user);
    await user.clear(screen.getByLabelText(fr.programmation.plannedStart));
    await user.type(screen.getByLabelText(fr.programmation.plannedStart), "2027-01-04");
    await user.clear(screen.getByLabelText(fr.programmation.plannedEnd));
    await user.type(screen.getByLabelText(fr.programmation.plannedEnd), "2027-02-04");
    await user.click(screen.getByRole("button", { name: s.save }));
    expect(
      await screen.findByText("La mission prévue doit commencer pendant l'année 2026."),
    ).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("shows a server 422 under the field and focuses it", async () => {
    serve();
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, () =>
        HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { objet_auditable: ["Cet objet n'appartient pas au processus."] },
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPlan(NEW_PATH, "RAI");
    await fillBase(user);
    await user.click(screen.getByRole("button", { name: s.save }));
    expect(await screen.findByText("Cet objet n'appartient pas au processus.")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText(fr.programmation.auditableObject)).toHaveFocus(),
    );
  });

  it("clears the auditable object when the process changes", async () => {
    serve();
    const user = userEvent.setup();
    renderPlan(NEW_PATH, "RAI");
    await screen.findByRole("option", { name: /FEP - Approvisionnement/ });
    await user.selectOptions(screen.getByLabelText(fr.programmation.process), "p1");
    const objet = screen.getByLabelText(fr.programmation.auditableObject);
    await screen.findByRole("option", { name: "Marchés" });
    await user.selectOptions(objet, "op1");
    expect(objet).toHaveValue("op1");
    await user.selectOptions(screen.getByLabelText(fr.programmation.process), "p2");
    expect(objet).toHaveValue("");
  });

  it("filters entities locally", async () => {
    serve();
    const user = userEvent.setup();
    renderPlan(NEW_PATH, "RAI");
    await screen.findByLabelText(/SCP - Service comptable/);
    await user.type(screen.getByRole("searchbox", { name: s.entitiesSearch }), "zzz");
    expect(screen.queryByLabelText(/SCP - Service comptable/)).not.toBeInTheDocument();
    expect(screen.getByText(s.entitiesNone)).toBeInTheDocument();
  });

  it("disables the form without a save button when the plan is validated", async () => {
    serve(aPlan({ statut: "VALIDE" }));
    renderPlan(NEW_PATH, "RAI");
    expect(await screen.findByLabelText(s.lineTitle)).toBeDisabled();
    expect(screen.getByText(s.readOnly)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: s.save })).not.toBeInTheDocument();
  });

  it("is read-only for an AUDITEUR", async () => {
    serve();
    server.use(
      http.get(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () => HttpResponse.json(aLine())),
    );
    renderPlan(EDIT_PATH, "AUDITEUR");
    expect(await screen.findByLabelText(s.lineTitle)).toBeDisabled();
    expect(screen.getByText(s.readOnly)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: s.save })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: s.deleteLine })).not.toBeInTheDocument();
  });

  it("shows the stored process and auditable object when editing", async () => {
    const pid = "c1a2b3d4-0000-4000-8000-000000000001";
    const oid = "c1a2b3d4-0000-4000-8000-000000000002";
    serve();
    server.use(
      http.get(`${API_URL}/api/v1/processes/`, () =>
        HttpResponse.json(page([{ ...PROCESS, id: pid }, PROCESS2])),
      ),
      http.get(`${API_URL}/api/v1/auditable-objects/tree/`, () =>
        HttpResponse.json([
          {
            id: "dom9",
            libelle: "Achats",
            description: "",
            ordre: 1,
            operations: [
              { id: oid, processus: pid, parent: "dom9", nature: "OPERATION", libelle: "Marchés" },
            ],
          },
        ]),
      ),
      http.get(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () => HttpResponse.json(aLine())),
    );
    renderPlan(EDIT_PATH, "AUDITEUR");
    await waitFor(() => expect(screen.getByLabelText(fr.programmation.process)).toHaveValue(pid));
    await waitFor(() =>
      expect(screen.getByLabelText(fr.programmation.auditableObject)).toHaveValue(oid),
    );
  });

  it("patches only the changed fields and labels deleted references", async () => {
    serve();
    let body: unknown;
    server.use(
      http.get(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () =>
        HttpResponse.json(
          aLine({
            processus_supprime: true,
            objet_auditable_supprime: true,
            entites_detail: [
              { id: "dx", code: "OLD", libelle: "Ancienne direction", supprime: true },
            ],
          }),
        ),
      ),
      http.patch(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aLine());
      }),
    );
    const user = userEvent.setup();
    renderPlan(EDIT_PATH, "RAI");
    expect(
      await screen.findByRole("option", { name: /Approvisionnement.*\(supprimé\)/ }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText(/OLD - Ancienne direction.*\(supprimé\)/)).toBeChecked();
    const title = screen.getByLabelText(s.lineTitle);
    await user.clear(title);
    await user.type(title, "Nouveau titre");
    await user.click(screen.getByRole("button", { name: s.save }));
    await waitFor(() => expect(body).toEqual({ titre: "Nouveau titre" }));
  });

  it("shows an error with retry when a reference list fails to load", async () => {
    serve();
    server.use(
      http.get(`${API_URL}/api/v1/processes/`, () => new HttpResponse(null, { status: 500 })),
    );
    renderPlan(NEW_PATH, "RAI");
    expect(await screen.findByRole("button", { name: fr.common.retry })).toBeInTheDocument();
  });

  it("deletes a line and returns to the plan", async () => {
    serve();
    let deleted = false;
    server.use(
      http.get(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () => HttpResponse.json(aLine())),
      http.delete(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    const { router } = renderPlan(EDIT_PATH, "RAI");
    await user.click(await screen.findByRole("button", { name: s.deleteLine }));
    await user.click(await screen.findByRole("button", { name: fr.common.delete }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/programme-annuel/${PLAN_ID}`),
    );
    expect(deleted).toBe(true);
  });

  it("has no axe violations", async () => {
    serve();
    const { container } = renderPlan(NEW_PATH, "RAI");
    await screen.findByLabelText(s.lineTitle);
    await screen.findByRole("option", { name: /FEP - Approvisionnement/ });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
