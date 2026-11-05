import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { aStep } from "@/features/missions/testUtils";
import type { paths } from "@/api/schema";
import { API_URL } from "@/test/msw";
import { aMission, baseHandlers, renderWithClient } from "../testUtils";
import { StepXZone } from "./StepXZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const step = aStep({ numero: 10, statut: "EN_COURS" });
const HASH = "3f2a" + "0".repeat(56) + "9c1b";

/**
 * Réponse réelle de l'API : un tableau nu (vue non paginée), typé sur le schéma OpenAPI pour que
 * le mock ne puisse plus diverger du contrat (un mock paginé masquait le plantage de l'étape X).
 */
type SnapshotList =
  paths["/api/v1/work-programs/snapshots/"]["get"]["responses"][200]["content"]["application/json"];

const snapshots: SnapshotList = [
  {
    id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    valide_par: {
      id: 3,
      username: "rai",
      nom_complet: "Fatou Kone",
      role: "RAI" as const,
      direction_code: "DAI",
      fonction: "RAI",
    },
    valide_le: "2026-10-27T10:00:00Z",
    empreinte: HASH,
  },
];

function handlers(list: SnapshotList = snapshots) {
  return [
    http.get(`${API_URL}/api/v1/work-programs/snapshots/`, () => HttpResponse.json(list)),
    ...baseHandlers(),
  ];
}

describe("StepXZone", () => {
  it("shows the summary, the validated snapshots and the milestone reminder", async () => {
    renderWithClient(<StepXZone mission={aMission()} step={step} />, handlers());
    const line = await screen.findByText(/Programme validé le 27\/10\/2026 par Fatou Kone/);
    expect(line).toHaveTextContent("Empreinte 3f2a…9c1b");
    expect(screen.getByText("Total : 44,5 j · Budget : 40 j")).toBeInTheDocument();
    expect(
      screen.getByText("La validation se fait avec le bouton “Valider le jalon”."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Valider/ })).not.toBeInTheDocument();
  });

  it("says so when no snapshot exists yet", async () => {
    renderWithClient(<StepXZone mission={aMission()} step={step} />, handlers([]));
    expect(await screen.findByText(/Aucune version du programme/)).toBeInTheDocument();
  });

  it("does not render a snapshot load error as empty", async () => {
    renderWithClient(<StepXZone mission={aMission()} step={step} />, [
      http.get(`${API_URL}/api/v1/work-programs/snapshots/`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
      ...baseHandlers(),
    ]);
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    expect(screen.queryByText(/Aucune version du programme/)).not.toBeInTheDocument();
  });

  it("prints with the mission reference in the A4 header", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    renderWithClient(<StepXZone mission={aMission()} step={step} />, handlers());
    await userEvent.click(await screen.findByRole("button", { name: "Imprimer le programme" }));
    expect(print).toHaveBeenCalledOnce();
    expect(screen.getByText("Mission MI-2026-001 : Audit des achats")).toBeInTheDocument();
    print.mockRestore();
  });

  it("has no axe violation", async () => {
    const { container } = renderWithClient(
      <StepXZone mission={aMission()} step={step} />,
      handlers(),
    );
    await screen.findByText(/Programme validé le/);
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
