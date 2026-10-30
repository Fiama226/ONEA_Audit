import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { StackedBar } from "./StackedBar";

const rows = [
  { key: "dg", label: "DG", segments: { done: 5, open: 3, late: 4 } },
  { key: "dr", label: "DRH", segments: { done: 1, open: 0, late: 0 }, href: "/x" },
];

describe("StackedBar", () => {
  it("shows a legend with the three labels", () => {
    render(<StackedBar rows={rows} ariaLabel="Actions par direction" />, { wrapper: MemoryRouter });
    const legend = screen.getByRole("list", { name: "Légende" });
    expect(within(legend).getByText("Clôturées")).toBeInTheDocument();
    expect(within(legend).getByText("Ouvertes dans les délais")).toBeInTheDocument();
    expect(within(legend).getByText("En retard")).toBeInTheDocument();
  });

  it("shows totals as text", () => {
    render(<StackedBar rows={rows} ariaLabel="Actions par direction" />, { wrapper: MemoryRouter });
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("reveals a real table with four columns on click", async () => {
    render(<StackedBar rows={rows} ariaLabel="Actions par direction" />, { wrapper: MemoryRouter });
    expect(screen.queryByRole("table")).toBeNull();
    const btn = screen.getByRole("button", { name: "Afficher le tableau" });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(btn);
    const table = screen.getByRole("table", { name: "Actions par direction" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((c) => c.textContent),
    ).toEqual(["Direction", "Clôturées", "Ouvertes dans les délais", "En retard"]);
    expect(screen.getByRole("button", { name: "Masquer le tableau" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("shows a segment tooltip on focus", async () => {
    render(<StackedBar rows={rows} ariaLabel="Actions par direction" />, { wrapper: MemoryRouter });
    await userEvent.tab(); // première ligne
    expect(screen.getByRole("tooltip")).toHaveTextContent("En retard : 4 sur 12");
  });

  it("has no axe violation", async () => {
    const { container } = render(<StackedBar rows={rows} ariaLabel="Actions par direction" />, {
      wrapper: MemoryRouter,
    });
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
