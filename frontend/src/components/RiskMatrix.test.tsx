import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RiskMatrix, riskLevel } from "./RiskMatrix";

describe("riskLevel", () => {
  it.each([
    [1, "low"],
    [7, "low"],
    [8, "medium"],
    [14, "medium"],
    [15, "high"],
    [25, "high"],
  ] as const)("score %i is %s", (score, level) => {
    expect(riskLevel(score)).toBe(level);
  });
});

describe("RiskMatrix", () => {
  it("is a named table with probability rows and impact columns", () => {
    render(<RiskMatrix />);
    const table = screen.getByRole("table", { name: /5 × 5/ });
    expect(within(table).getAllByRole("rowheader")).toHaveLength(5);
    expect(within(table).getAllByRole("columnheader")).toHaveLength(5);
    expect(within(table).getAllByRole("cell")).toHaveLength(25);
  });

  it("describes each cell for assistive technology", () => {
    render(<RiskMatrix />);
    expect(
      screen.getByRole("cell", { name: "Probabilité 5, impact 5 : 25, élevé" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("cell", { name: "Probabilité 1, impact 2 : 2, faible" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("cell", { name: "Probabilité 3, impact 3 : 9, moyen" }),
    ).toBeInTheDocument();
  });

  it("shows the number of risks of a cell when data is provided", () => {
    render(<RiskMatrix cells={[{ probability: 5, impact: 5, count: 99 }]} />);
    const cell = screen.getByRole("cell", { name: /Probabilité 5, impact 5 : 99/ });
    expect(cell).toHaveAttribute("data-level", "high");
    expect(cell).toHaveTextContent("99");
  });
});
