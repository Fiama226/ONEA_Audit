import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { PrintLayout } from "./PrintLayout";

const at = new Date("2026-10-27T23:30:00Z");

describe("PrintLayout", () => {
  it("renders title, reference, ONEA header and Ouagadougou print date", () => {
    render(
      <PrintLayout title="Programme annuel" reference="MIS-2026-001" printedAt={at}>
        <p>Contenu</p>
      </PrintLayout>,
    );
    expect(screen.getByText("Programme annuel")).toBeInTheDocument();
    expect(screen.getByText("MIS-2026-001")).toBeInTheDocument();
    expect(screen.getByText(fr.print.organisation)).toBeInTheDocument();
    expect(screen.getByText(`${fr.impression.printedOn} 27/10/2026 23:30`)).toBeInTheDocument();
    expect(screen.getByText("Contenu")).toBeInTheDocument();
    expect(screen.getByText("Programme annuel").parentElement?.className).toContain("print:block");
  });

  it("omits the reference when absent and switches to landscape", () => {
    const { container } = render(
      <PrintLayout title="Matrice" orientation="paysage" printedAt={at}>
        <p>x</p>
      </PrintLayout>,
    );
    expect(screen.queryByText(fr.impression.reference)).toBeNull();
    expect(container.firstElementChild).toHaveClass("print-paysage");
  });

  it("hides screen actions through print:hidden", () => {
    render(
      <PrintLayout title="T" printedAt={at}>
        <button className="print:hidden">Imprimer</button>
      </PrintLayout>,
    );
    expect(screen.getByRole("button", { name: "Imprimer" })).toHaveClass("print:hidden");
  });
});
