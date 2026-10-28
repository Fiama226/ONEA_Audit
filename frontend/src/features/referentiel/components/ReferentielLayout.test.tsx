import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { ReferentielLayout } from "./ReferentielLayout";

describe("ReferentielLayout", () => {
  it("hides the section tabs when printing", () => {
    render(
      <MemoryRouter>
        <ReferentielLayout />
      </MemoryRouter>,
    );
    expect(screen.getByRole("navigation", { name: fr.referentiel.tabsLabel })).toHaveClass(
      "print:hidden",
    );
  });
});
