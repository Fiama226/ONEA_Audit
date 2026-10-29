import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { aMission } from "@/features/missions/testUtils";
import { fr } from "@/i18n/fr";
import { aGrid } from "../testUtils";
import { SegregationGridEditor } from "./SegregationGridEditor";

const t = fr.analyseIII;
const PROCESS = { id: "88888888-8888-4888-8888-888888888888", code: "P-ACH", libelle: "Achats" };

function show(editable: boolean, grid?: ReturnType<typeof aGrid>) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SegregationGridEditor
        mission={aMission()}
        processus={PROCESS}
        grid={grid}
        editable={editable}
      />
    </QueryClientProvider>,
  );
}

const printStyle = () => document.querySelector("style[media=print]");

describe("SegregationGridEditor", () => {
  it("uses the named landscape page only for a grid with content", () => {
    const { container, unmount } = show(true);
    expect(printStyle()).toBeNull();
    expect(container.querySelector("article")?.className).not.toContain("page:grille");
    unmount();
    const full = show(true, aGrid({ taches: ["T"], acteurs: ["A"] }));
    expect(printStyle()?.textContent).toBe("@page grille { size: A4 landscape; }");
    expect(full.container.querySelector("article")?.className).toContain("[page:grille]");
  });

  it("renames, removes tasks and actors and reindexes the cells", async () => {
    show(
      true,
      aGrid({
        taches: ["T1", "T2"],
        acteurs: ["A1", "A2"],
        cellules: [{ tache: 1, acteur: 1, roles: ["CONTROLE"] }],
      }),
    );
    expect(screen.getByRole("checkbox", { name: "T2 — A2 — Contrôle" })).toBeChecked();
    await userEvent.click(
      screen.getByRole("button", { name: t.gridRemoveTask.replace("{n}", "1") }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: t.gridRemoveActor.replace("{n}", "1") }),
    );
    expect(screen.getByRole("checkbox", { name: "T2 — A2 — Contrôle" })).toBeChecked();
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
    expect(screen.getByText(t.gridDirty)).toBeInTheDocument();
  });

  it("validates labels before sending and clears the error on edit", async () => {
    show(true, aGrid({ taches: ["T1"], acteurs: ["A1"] }));
    await userEvent.clear(screen.getByLabelText(t.gridTaskName.replace("{n}", "1")));
    await userEvent.click(screen.getByRole("button", { name: t.gridSave }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t.gridLabelRequired);
    await userEvent.type(screen.getByLabelText(t.gridTaskName.replace("{n}", "1")), "X");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows server alerts and the legend, read-only as plain text", () => {
    show(
      false,
      aGrid({
        taches: ["Payer"],
        acteurs: ["Caissier"],
        analyse: { taches_sans_acteur: ["Payer"], taches_multi_executants: [], cumuls: [] },
      }),
    );
    expect(screen.getByText("Tâche sans acteur : Payer")).toBeInTheDocument();
    expect(screen.getByText(t.gridLegend)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
