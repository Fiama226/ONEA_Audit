import { render, screen } from "@testing-library/react";
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
  it("shows the score scale when there is no data", () => {
    render(<RiskMatrix />);
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("shows the number of risks of a cell when data is provided", () => {
    render(<RiskMatrix cells={[{ probability: 5, impact: 5, count: 99 }]} />);
    const cell = screen.getByText("99");
    expect(cell.closest("[data-level]")).toHaveAttribute("data-level", "high");
  });
});
