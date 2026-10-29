import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { aLine, aPlan, aSummary, listHandler, PLAN_ID, renderPlan } from "../testUtils";

vi.mock("../components/AuditPlanCalendar", () => ({
  AuditPlanCalendar: (props: { year: number; lines: unknown[] }) => (
    <div data-testid="calendar">{`Calendrier ${props.year} : ${props.lines.length}`}</div>
  ),
}));

const path = `/programme-annuel/${PLAN_ID}`;
const planUrl = `${API_URL}/api/v1/audit-plans/${PLAN_ID}/`;
const PROCESS = {
  id: "c1a2b3d4-0000-4000-8000-000000000001",
  code: "FEP",
  libelle: "Approvisionnement",
};
const LINES = [
  aLine({ id: "l-q2", numero: 1, titre: "Audit des achats", trimestre: 2 }),
  aLine({
    id: "l-q1",
    numero: 2,
    titre: "Revue de la paie",
    trimestre: 1,
    debut_prevu: "2026-02-02",
    fin_prevue: "2026-02-27",
    processus_supprime: true,
  }),
  aLine({
    id: "l-q3",
    numero: 3,
    titre: "Audit des stocks",
    trimestre: 3,
    debut_prevu: "2026-08-03",
    fin_prevue: "2026-08-28",
  }),
];

function mock(
  opts: { plan?: Parameters<typeof aPlan>[0]; lines?: unknown[]; processes?: unknown[] } = {},
) {
  server.use(
    http.get(planUrl, () => HttpResponse.json(aPlan(opts.plan))),
    http.get(`${planUrl}summary/`, () =>
      HttpResponse.json(
        aSummary({
          nb_lignes: 3,
          charge_totale_jours: "60.0",
          par_type: { ASSURANCE: 2, CONSEIL: 1 },
          par_trimestre: { 1: 1, 2: 1, 3: 1, 4: 0 },
        }),
      ),
    ),
    listHandler("audit-plan-lines", opts.lines ?? LINES),
    listHandler("processes", opts.processes ?? [PROCESS]),
  );
}

const rules = { "color-contrast": { enabled: false } };
let restoreUrl: (() => void) | undefined;
afterEach(() => {
  restoreUrl?.();
  restoreUrl = undefined;
  vi.restoreAllMocks();
});

describe("AuditPlanDetailPage", () => {
  it("shows the four draft actions to the RAI", async () => {
    mock();
    renderPlan(path, "RAI");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Programme annuel d'audit interne 2026",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Brouillon")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajouter une mission prévue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Modifier" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Valider le programme" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Supprimer le programme" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exporter en CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Imprimer" })).toBeInTheDocument();
  });

  it("freezes a validated plan: banner, export, no write action", async () => {
    mock({
      plan: {
        statut: "VALIDE",
        valide_le: "2026-01-20T09:00:00Z",
        valide_par: { id: 2, nom_complet: "Awa Ouedraogo" } as never,
      },
    });
    renderPlan(path, "RAI");
    expect(await screen.findByText(/Programme validé le 20\/01\/2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exporter en Excel" })).toBeInTheDocument();
    for (const name of [
      "Ajouter une mission prévue",
      "Modifier",
      "Valider le programme",
      "Supprimer le programme",
    ]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("gives the DG no write action", async () => {
    mock();
    renderPlan(path, "DG");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("button", { name: "Exporter en CSV" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Valider le programme" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Modifier" })).not.toBeInTheDocument();
  });

  it("shows the summary counts", async () => {
    mock();
    renderPlan(path, "AUDITEUR");
    const summary = await screen.findByRole("region", { name: "Synthèse" });
    await within(summary).findByText("60");
    expect(summary).toHaveTextContent("Assurance");
    expect(summary).toHaveTextContent("1er trimestre");
  });

  it("groups lines by quarter in chronological order", async () => {
    mock();
    renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des achats" });
    const bodies = screen.getAllByRole("rowgroup").slice(1);
    expect(bodies).toHaveLength(3);
    expect(bodies[0]).toHaveTextContent("1er trimestre · 1 mission prévue");
    expect(bodies[1]).toHaveTextContent("2e trimestre · 1 mission prévue");
    expect(bodies[2]).toHaveTextContent("3e trimestre · 1 mission prévue");
    expect(within(bodies[0]!).getByText("(supprimé)", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Audit des achats" })).toHaveAttribute(
      "href",
      "/programme-annuel/lignes/l-q2",
    );
  });

  it("reflects the quarter filter in the URL and applies it", async () => {
    mock();
    const user = userEvent.setup();
    const { router } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des achats" });
    await user.selectOptions(screen.getByLabelText("Trimestre"), "3");
    expect(router.state.location.search).toContain("trimestre=3");
    expect(screen.queryByRole("link", { name: "Audit des achats" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Audit des stocks" })).toBeInTheDocument();
  });

  it("shows a filtered empty state and clears the filters", async () => {
    mock();
    const user = userEvent.setup();
    renderPlan(`${path}?trimestre=4`, "AUDITEUR");
    expect(
      await screen.findByText("Aucune mission prévue ne correspond aux filtres."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Effacer les filtres" }));
    expect(await screen.findByRole("link", { name: "Audit des achats" })).toBeInTheDocument();
  });

  it("explains an empty plan, with the add action for the RAI only", async () => {
    mock({ lines: [] });
    const { unmount } = renderPlan(path, "RAI");
    expect(
      await screen.findByText("Ce programme ne contient encore aucune mission prévue."),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Ajouter une mission prévue" }).length,
    ).toBeGreaterThan(0);
    unmount();
    mock({ lines: [] });
    renderPlan(path, "AUDITEUR");
    expect(
      await screen.findByText("Ce programme ne contient aucune mission prévue pour le moment."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ajouter une mission prévue" }),
    ).not.toBeInTheDocument();
  });

  it("asks the RAI to create processes first when the referential has none", async () => {
    mock({ lines: [], processes: [] });
    renderPlan(path, "RAI");
    expect(
      await screen.findByText("Créez d'abord les processus dans le référentiel."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Aller au référentiel des processus" }),
    ).toBeInTheDocument();
  });

  it("keeps the validation dialog open and shows the 422 for an empty plan", async () => {
    mock({ lines: [] });
    server.use(
      http.post(`${planUrl}validate/`, () =>
        HttpResponse.json(
          { detail: "Un programme vide ne peut pas être validé." },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Valider le programme" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "Une fois validé, le programme est figé : aucune mission prévue ne pourra plus être ajoutée, modifiée ou retirée.",
      ),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Valider définitivement" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Un programme vide ne peut pas être validé.",
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("edits the label and comment", async () => {
    mock();
    let body: unknown;
    server.use(
      http.patch(planUrl, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aPlan());
      }),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Modifier" }));
    const dialog = await screen.findByRole("dialog");
    const comment = within(dialog).getByLabelText("Commentaire");
    await user.type(comment, "Note");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(body).toMatchObject({ libelle: "Programme annuel 2026", commentaire: "Note" }),
    );
  });

  it("deletes the plan then returns to the list", async () => {
    mock();
    let deleted = false;
    let readsAfterDelete = 0;
    const gone = () => {
      readsAfterDelete += 1;
      return HttpResponse.json({ detail: "Introuvable." }, { status: 404 });
    };
    server.use(
      http.delete(planUrl, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
      // Une fois supprimé, le programme n'existe plus : lire son détail ou sa synthèse donne 404.
      http.get(planUrl, () => (deleted ? gone() : HttpResponse.json(aPlan()))),
      http.get(`${planUrl}summary/`, () => (deleted ? gone() : HttpResponse.json(aSummary()))),
      listHandler("audit-plans", []),
    );
    const user = userEvent.setup();
    const { router } = renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Supprimer le programme" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Supprimer" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/programme-annuel"));
    expect(
      await screen.findByText("Aucun programme annuel n'a encore été créé."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Ce programme annuel est introuvable.")).not.toBeInTheDocument();
    expect(readsAfterDelete).toBe(0);
  });

  it("shows the 422 of an edit inside the dialog", async () => {
    mock();
    server.use(
      http.patch(planUrl, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { libelle: ["Ce libellé est déjà utilisé."] } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Modifier" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(await within(dialog).findByText("Ce libellé est déjà utilisé.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("gives the ADMIN a read-only view", async () => {
    mock();
    renderPlan(path, "ADMIN");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("button", { name: "Exporter en CSV" })).toBeInTheDocument();
    for (const name of ["Ajouter une mission prévue", "Modifier", "Valider le programme"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("shows the editable label under the title", async () => {
    mock({ plan: { libelle: "Programme révisé 2026" } });
    renderPlan(path, "AUDITEUR");
    expect(await screen.findByText("Programme révisé 2026")).toBeInTheDocument();
  });

  it("hides the add action when the referential has no process", async () => {
    mock({ processes: [], lines: [] });
    renderPlan(path, "RAI");
    await screen.findByText("Créez d'abord les processus dans le référentiel.");
    expect(
      screen.queryByRole("button", { name: "Ajouter une mission prévue" }),
    ).not.toBeInTheDocument();
  });

  it("filters by process, type and search text", async () => {
    mock({
      lines: [
        ...LINES,
        aLine({
          id: "l-conseil",
          numero: 4,
          titre: "Conseil sur la trésorerie",
          type: "CONSEIL",
          processus: "other-process",
          processus_code: "FIN",
          processus_libelle: "Finances",
        }),
      ],
      processes: [PROCESS, { id: "other-process", code: "FIN", libelle: "Finances" }],
    });
    const user = userEvent.setup();
    const { router } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des achats" });
    await user.selectOptions(screen.getByLabelText("Type"), "CONSEIL");
    expect(router.state.location.search).toContain("type=CONSEIL");
    expect(screen.getAllByRole("link", { name: /^(Audit|Revue|Conseil)/ })).toHaveLength(1);
    await user.selectOptions(screen.getByLabelText("Type"), "");
    await user.selectOptions(screen.getByLabelText("Processus"), "other-process");
    expect(router.state.location.search).toContain("processus=other-process");
    expect(screen.getByRole("link", { name: "Conseil sur la trésorerie" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit des achats" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Processus"), "");
    await user.type(screen.getByLabelText("Recherche"), "stocks");
    expect(router.state.location.search).toContain("q=stocks");
    expect(screen.getByRole("link", { name: "Audit des stocks" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit des achats" })).not.toBeInTheDocument();
  });

  it("prints the full table even when filters are applied", async () => {
    mock();
    const { container } = renderPlan(`${path}?trimestre=3`, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des stocks" });
    const printCopy = container.querySelector("[data-print-full]");
    expect(printCopy).not.toBeNull();
    expect(printCopy).toHaveClass("hidden", "print:block");
    expect(printCopy?.querySelectorAll("tbody")).toHaveLength(3);
    // La copie complète n'existe que si les filtres masquent des lignes.
    expect(printCopy).toHaveAttribute("aria-hidden", "true");
  });

  it("does not duplicate the table for print when nothing is filtered", async () => {
    mock();
    const { container } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des stocks" });
    expect(container.querySelector("[data-print-full]")).toBeNull();
  });

  it("keeps the table header sticky inside its own scroll container", async () => {
    mock();
    const { container } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des stocks" });
    const wrapper = container.querySelector("table")?.parentElement;
    expect(wrapper?.className).toMatch(/max-h-/);
    expect(wrapper).toHaveClass("overflow-auto", "print:overflow-visible", "print:max-h-none");
    const header = container.querySelector("thead th");
    expect(header).toHaveClass("sticky", "top-0");
  });

  it("shows a dash for a zero load and uses a rowgroup header per quarter", async () => {
    mock({ lines: [aLine({ charge_prevue_jours: "0.0" })] });
    const { container } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des achats" });
    const cells = container.querySelectorAll("tbody tr:nth-child(2) td");
    expect(cells[cells.length - 1]).toHaveTextContent("-");
    expect(container.querySelector("tbody th")).toHaveAttribute("scope", "rowgroup");
  });

  it("locks the validation dialog while running, then moves focus to the title", async () => {
    mock();
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post(`${planUrl}validate/`, async () => {
        await gate;
        return HttpResponse.json(aPlan({ statut: "VALIDE" }));
      }),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Valider le programme" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Valider définitivement" }));
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "Annuler" })).toBeDisabled(),
    );
    await user.keyboard("{Escape}");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    release();
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveFocus());
  });

  it("calls the xlsx export endpoint", async () => {
    mock();
    let type = "";
    server.use(
      http.get(`${planUrl}export/`, ({ request }) => {
        type = new URL(request.url).searchParams.get("type") ?? "";
        return new HttpResponse("data", {
          headers: { "Content-Disposition": 'attachment; filename="programme.xlsx"' },
        });
      }),
    );
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    restoreUrl = () => {
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    };
    const saved: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      saved.push(this.download);
    });
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Exporter en Excel" }));
    await waitFor(() => expect(saved).toEqual(["programme.xlsx"]));
    expect(URL.createObjectURL).toHaveBeenCalledOnce();
    await waitFor(() => expect(type).toBe("xlsx"));
  });

  it("shows an export error without leaving the page", async () => {
    mock();
    server.use(
      http.get(`${planUrl}export/`, () =>
        HttpResponse.json({ detail: "Export indisponible." }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderPlan(path, "RAI");
    await user.click(await screen.findByRole("button", { name: "Exporter en CSV" }));
    expect(await screen.findByText("Export indisponible.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("shows the flash message sent by the line form, dismissible and cleared from history", async () => {
    mock();
    const user = userEvent.setup();
    const { router } = renderPlan("/programme-annuel", "RAI");
    await router.navigate(path, { state: { flash: "Mission prévue enregistrée." } });
    const flash = await screen.findByText("Mission prévue enregistrée.");
    expect(flash.closest("[role=status]")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.state).toBeNull());
    expect(screen.getByText("Mission prévue enregistrée.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fermer le message" }));
    expect(screen.queryByText("Mission prévue enregistrée.")).not.toBeInTheDocument();
  });

  it("prints with window.print", async () => {
    mock();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const user = userEvent.setup();
    renderPlan(path, "AUDITEUR");
    await user.click(await screen.findByRole("button", { name: "Imprimer" }));
    expect(print).toHaveBeenCalledOnce();
  });

  it("mounts the calendar in the Calendrier tab, reflected in the URL", async () => {
    mock();
    const user = userEvent.setup();
    const { router } = renderPlan(path, "AUDITEUR");
    await screen.findByRole("link", { name: "Audit des achats" });
    expect(screen.getByRole("tab", { name: "Liste" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("tab", { name: "Calendrier" }));
    expect(router.state.location.search).toContain("vue=calendrier");
    const calendar = await screen.findByTestId("calendar");
    expect(calendar).toBeVisible();
    expect(calendar).toHaveTextContent("Calendrier 2026 : 3");
  });

  it("has no axe violations, dialogs included", async () => {
    mock();
    const user = userEvent.setup();
    const { container } = renderPlan(path, "RAI");
    await screen.findByRole("link", { name: "Audit des achats" });
    expect((await axe(container, { rules })).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Valider le programme" }));
    const validate = await screen.findByRole("alertdialog");
    expect((await axe(validate, { rules })).violations).toEqual([]);
    await user.click(within(validate).getByRole("button", { name: "Annuler" }));
    await user.click(screen.getByRole("button", { name: "Modifier" }));
    const edit = await screen.findByRole("dialog");
    expect((await axe(edit, { rules })).violations).toEqual([]);
  });
});
