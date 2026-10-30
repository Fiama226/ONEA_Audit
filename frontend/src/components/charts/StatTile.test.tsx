import { render, screen } from "@testing-library/react";
import { AlertTriangle } from "lucide-react";
import { describe, expect, it } from "vitest";
import { StatTile } from "./StatTile";

describe("StatTile", () => {
  it("renders a dash for null", () => {
    render(<StatTile label="Actions" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("formats the value", () => {
    render(<StatTile label="Actions" value={1234} />);
    expect(screen.getByText(/1\s?234/)).toBeInTheDocument();
  });

  it("throws in development when a non-neutral tone has no icon", () => {
    expect(() => render(<StatTile label="Retards" value={3} tone="danger" />)).toThrow(/icône/);
  });

  it("accepts a toned tile with icon, value stays foreground", () => {
    render(<StatTile label="Retards" value={3} tone="danger" icon={AlertTriangle} />);
    expect(screen.getByText("3")).toHaveClass("text-foreground");
  });
});
