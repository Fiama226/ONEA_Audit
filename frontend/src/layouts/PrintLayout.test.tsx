import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { PrintLayout } from "./PrintLayout";

describe("PrintLayout", () => {
  it("renders the mission reference, the body and the confidentiality note", () => {
    render(
      <PrintLayout
        reference="MIS-2026-001"
        documentType="Rapport d'audit"
        printedBy="A. Ouedraogo"
        printedAt="27/10/2026 à 08:14"
      >
        <p>Contenu du document</p>
      </PrintLayout>,
    );
    expect(screen.getByText("MIS-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Rapport d'audit")).toBeInTheDocument();
    expect(screen.getByText("Contenu du document")).toBeInTheDocument();
    expect(screen.getByText("CONFIDENTIEL · USAGE INTERNE ONEA")).toBeInTheDocument();
    expect(screen.getByText(fr.print.organisation)).toBeInTheDocument();
    expect(
      screen.getByText(/Imprimé le 27\/10\/2026 à 08:14 par A\. Ouedraogo/),
    ).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });
});
