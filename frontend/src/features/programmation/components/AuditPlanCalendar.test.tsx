import { render, screen, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { MONTH_LABELS } from "../labels";
import { aLine } from "../testUtils";
import { AuditPlanCalendar } from "./AuditPlanCalendar";

function plannedMonths(row: HTMLElement): string[] {
  const cells = within(row).getAllByRole("cell");
  return MONTH_LABELS.filter((_, i) => within(cells[i]!).queryByText("prévue") !== null);
}

describe("AuditPlanCalendar", () => {
  it("marks only the months covered by the period", () => {
    render(
      <AuditPlanCalendar
        year={2026}
        lines={[aLine({ debut_prevu: "2026-03-02", fin_prevue: "2026-04-30" })]}
      />,
    );
    expect(screen.getByRole("table", { name: "Calendrier du programme 2026" })).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /Audit des achats/ });
    expect(plannedMonths(row)).toEqual(["mars", "avr."]);
    expect(within(row).queryByText(/→/)).not.toBeInTheDocument();
  });

  it("shows the overflow into the next year", () => {
    render(
      <AuditPlanCalendar
        year={2026}
        lines={[aLine({ debut_prevu: "2026-12-01", fin_prevue: "2027-01-31" })]}
      />,
    );
    const row = screen.getByRole("row", { name: /Audit des achats/ });
    expect(plannedMonths(row)).toEqual(["déc."]);
    expect(within(row).getByText("→ janv. 2027")).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = render(<AuditPlanCalendar year={2026} lines={[aLine()]} />);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
