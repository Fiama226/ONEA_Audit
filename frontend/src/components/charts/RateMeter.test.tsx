import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RateMeter } from "./RateMeter";

describe("RateMeter", () => {
  it("shows 45 % (9 sur 20) with meter attributes", () => {
    render(<RateMeter label="Taux" rate={45} numerator={9} denominator={20} />);
    expect(screen.getByText("45 % (9 sur 20)")).toBeInTheDocument();
    const meter = screen.getByRole("meter", { name: "Taux" });
    expect(meter).toHaveAttribute("aria-valuenow", "45");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
  });

  it("shows a dash when there is no action", () => {
    render(<RateMeter label="Taux" rate={null} numerator={0} denominator={0} />);
    expect(screen.getByText("— (aucune action)")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).toBeNull();
  });
});
