import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { allSteps, MISSION_ID } from "../testUtils";
import { MissionStepper } from "./MissionStepper";

function setup(selected?: number) {
  const steps = allSteps((n) => ({
    statut: n <= 3 ? "VALIDEE" : n === 4 ? "EN_COURS" : "A_FAIRE",
  }));
  return render(
    <MemoryRouter>
      <MissionStepper steps={steps} missionId={MISSION_ID} selected={selected} />
    </MemoryRouter>,
  );
}

describe("MissionStepper", () => {
  it("renders three titled phase sections and 18 step links", () => {
    setup(4);
    expect(screen.getAllByRole("region")).toHaveLength(3);
    expect(screen.getByRole("region", { name: /Planification.*I–X/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Accomplissement.*XI–XIV/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Communication.*XV–XVIII/ })).toBeInTheDocument();
    expect(screen.getAllByRole("list")).toHaveLength(3);
    expect(screen.getAllByRole("link")).toHaveLength(18);
  });

  it("links each step to its page and marks only the selected one", () => {
    setup(4);
    const current = screen.getByRole("link", { current: "step" });
    expect(current).toHaveAttribute("href", `/missions/${MISSION_ID}/etapes/4`);
    expect(current).toHaveTextContent("IV");
    expect(screen.getAllByRole("link", { current: "step" })).toHaveLength(1);
  });

  it("shows status text and the milestone mention", () => {
    setup(4);
    expect(screen.getAllByText("Validée").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Jalon")).toHaveLength(4);
    const sixth = screen.getByRole("link", { name: /VI\b.*Jalon/ });
    expect(within(sixth).getByText("À faire")).toBeInTheDocument();
  });

  it("has no accessibility violation", async () => {
    const { container } = setup(4);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
