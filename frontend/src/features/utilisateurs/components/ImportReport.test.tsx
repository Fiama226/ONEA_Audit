import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aReport } from "../testUtils";
import { ImportReport } from "./ImportReport";

describe("ImportReport", () => {
  it("titles a dry run as a verification and lists rejection reasons", async () => {
    const { container } = render(<ImportReport report={aReport()} />);
    expect(screen.getByText("Vérification — aucun compte n'a encore été créé")).toBeInTheDocument();
    expect(screen.getByText("1 compte créé, 0 mis à jour, 1 ligne ignorée")).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /chef/ });
    expect(within(row).getByText("3")).toBeInTheDocument();
    expect(
      within(row).getByText("Le rôle ADMIN ne s'attribue que dans l'annuaire (Keycloak)."),
    ).toBeInTheDocument();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("titles a real import as finished, pluralises and shows role changes", () => {
    render(
      <ImportReport
        report={aReport({
          dry_run: false,
          crees: ["a.b", "c.d"],
          mis_a_jour: ["e.f (rôle AUDITEUR → RAI)"],
          ignores: [],
        })}
      />,
    );
    expect(screen.getByText("Import terminé")).toBeInTheDocument();
    expect(screen.getByText("2 comptes créés, 1 mis à jour, 0 ligne ignorée")).toBeInTheDocument();
    expect(screen.getByText("e.f (rôle AUDITEUR → RAI)")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a dash when a rejection has no line number", () => {
    render(
      <ImportReport
        report={aReport({
          ignores: [{ ligne: null, identifiant: "kc", motif: "Compte de service" }],
        })}
      />,
    );
    const row = screen.getByRole("row", { name: /kc/ });
    expect(within(row).getByText("—")).toBeInTheDocument();
  });

  it("announces the summary and focuses the heading", () => {
    render(<ImportReport report={aReport()} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 compte créé, 0 mis à jour");
    expect(
      screen.getByRole("heading", { name: "Vérification — aucun compte n'a encore été créé" }),
    ).toHaveFocus();
  });
});
