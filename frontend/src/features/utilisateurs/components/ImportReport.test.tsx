import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aReport } from "../testUtils";
import { ImportReport } from "./ImportReport";

describe("ImportReport", () => {
  it("titles a dry run as a verification and lists rejection reasons", async () => {
    const { container } = render(<ImportReport report={aReport()} />);
    expect(screen.getByText("Vérification — aucun compte n'a encore été créé")).toBeInTheDocument();
    expect(screen.getByText("1 compte créé, 1 ligne ignorée")).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /chef/ });
    expect(within(row).getByText("3")).toBeInTheDocument();
    expect(
      within(row).getByText("Le rôle Administrateur ne peut pas être attribué par import."),
    ).toBeInTheDocument();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("titles a real import as finished and pluralises", () => {
    render(
      <ImportReport
        report={aReport({
          dry_run: false,
          crees: ["a.b", "c.d"],
          ignores: [],
        })}
      />,
    );
    expect(screen.getByText("Import terminé")).toBeInTheDocument();
    expect(screen.getByText("2 comptes créés, 0 ligne ignorée")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("announces the summary and focuses the heading", () => {
    render(<ImportReport report={aReport()} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 compte créé, 1 ligne ignorée");
    expect(
      screen.getByRole("heading", { name: "Vérification — aucun compte n'a encore été créé" }),
    ).toHaveFocus();
  });
});
