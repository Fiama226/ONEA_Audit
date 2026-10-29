import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithAuth } from "@/test/shell";
import { ImportActions } from "./ImportActions";

describe("ImportActions", () => {
  it("opens each dialog from its button", async () => {
    renderWithAuth(<ImportActions />, "ADMIN");
    await userEvent.click(screen.getByRole("button", { name: "Importer depuis l'annuaire" }));
    expect(screen.getByRole("dialog", { name: "Importer depuis l'annuaire" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Importer un fichier CSV" }));
    expect(screen.getByRole("dialog", { name: "Importer un fichier CSV" })).toBeInTheDocument();
  });
});
