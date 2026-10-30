import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { ConfirmationTextDialog } from "./ConfirmationTextDialog";

const TEXTE = "Je confirme avoir lu le rapport.\nLe texte <b>exact</b> du serveur.";

function setup(onConfirm = vi.fn().mockResolvedValue(undefined)) {
  const utils = render(
    <ConfirmationTextDialog
      title="Valider le rapport"
      texte={TEXTE}
      confirmLabel="Valider"
      onConfirm={onConfirm}
    >
      <button type="button">Ouvrir</button>
    </ConfirmationTextDialog>,
  );
  return { ...utils, onConfirm };
}

describe("ConfirmationTextDialog", () => {
  it("bloque l'envoi tant que la case n'est pas cochée", async () => {
    const user = userEvent.setup();
    const { onConfirm } = setup();
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    const checkbox = screen.getByRole("checkbox", { name: fr.communication.confirmCheckbox });
    expect(checkbox).not.toBeChecked();
    const submit = screen.getByRole("button", { name: "Valider" });
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(checkbox);
    expect(submit).toBeEnabled();
  });

  it("affiche le texte du serveur tel quel", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    expect(
      screen.getByText((_, el) => el?.tagName === "P" && el.textContent === TEXTE),
    ).toBeInTheDocument();
  });

  it("annonce la confirmation avec la date et l'empreinte", async () => {
    const user = userEvent.setup();
    const onConfirm = vi
      .fn()
      .mockResolvedValue({ confirme_le: "2026-10-29T10:30:00Z", empreinte: "abc123" });
    setup(onConfirm);
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Valider" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Confirmé le 29/10/2026 à 10:30. Empreinte : abc123.",
    );
  });

  it("affiche l'erreur du serveur et garde le dialogue ouvert", async () => {
    const user = userEvent.setup();
    setup(vi.fn().mockRejectedValue(new Error("Rapport déjà validé.")));
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Valider" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Rapport déjà validé."),
    );
  });

  it("n'a aucune violation axe", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "Ouvrir" }));
    const dialog = screen.getByRole("alertdialog");
    expect(
      (await axe(dialog, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
