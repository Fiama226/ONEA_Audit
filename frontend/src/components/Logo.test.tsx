import { render, screen } from "@testing-library/react";
import { Logo, LOGO_ALT } from "@/components/Logo";

describe("Logo", () => {
  it("affiche le logo officiel ONEA avec son texte alternatif français", () => {
    render(<Logo subtitle="Audit interne" />);
    const img = screen.getByRole("img", { name: LOGO_ALT });
    expect(img).toHaveAttribute("alt", "ONEA — Office national de l'eau et de l'assainissement");
    expect(screen.getByText("Audit interne")).toBeInTheDocument();
  });

  it("n'affiche que le logo en mode compact", () => {
    render(<Logo compact subtitle="Audit interne" />);
    expect(screen.getByRole("img", { name: LOGO_ALT })).toBeInTheDocument();
    expect(screen.queryByText("Audit interne")).not.toBeInTheDocument();
  });
});
