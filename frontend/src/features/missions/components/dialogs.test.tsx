import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { MotifDialog } from "./MotifDialog";

function motif(onSubmit: (motif: string) => Promise<unknown>) {
  render(
    <MotifDialog
      open
      onOpenChange={() => undefined}
      title="Annuler"
      confirmLabel="Valider"
      onSubmit={onSubmit}
    />,
  );
}

describe("MotifDialog", () => {
  it("refuses an empty motif without calling the server", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    motif(onSubmit);
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(screen.getByRole("alert")).toHaveTextContent(fr.missions.motifRequired);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows the field error once when the server repeats it in detail", async () => {
    const message = "Le motif est trop court.";
    motif(() => Promise.reject(new ApiError(400, message, { motif: [message] })));
    await userEvent.type(screen.getByLabelText(fr.missions.motifLabel), "x");
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(message);
  });

  it("shows the detail of a business refusal and stays open", async () => {
    motif(() => Promise.reject(new ApiError(422, "Mission déjà annulée.", {})));
    await userEvent.type(screen.getByLabelText(fr.missions.motifLabel), "raison");
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mission déjà annulée.");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });
});

function confirmDialog(onConfirm: () => Promise<unknown>, requireCheck?: boolean) {
  const onOpenChange = vi.fn();
  render(
    <ConfirmActionDialog
      open
      onOpenChange={onOpenChange}
      title="Émettre"
      text="Texte à confirmer"
      confirmLabel="Valider"
      requireCheck={requireCheck}
      onConfirm={onConfirm}
    />,
  );
  return onOpenChange;
}

describe("ConfirmActionDialog", () => {
  it("keeps the button disabled until the box is checked", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onOpenChange = confirmDialog(onConfirm);
    const button = screen.getByRole("button", { name: "Valider" });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: fr.missions.confirmCheckbox }));
    await userEvent.click(button);
    await waitFor(() => expect(onConfirm).toHaveBeenCalledOnce());
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("lists the detail and the field messages of a refusal, without duplicates", async () => {
    confirmDialog(
      () =>
        Promise.reject(
          new ApiError(422, "Des informations obligatoires manquent.", {
            objectifs: ["Les objectifs sont obligatoires."],
            entites: ["Les objectifs sont obligatoires.", "Indiquez une entité."],
          }),
        ),
      false,
    );
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Des informations obligatoires manquent.");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("shows a generic message for a non-API failure", async () => {
    confirmDialog(() => Promise.reject(new Error("boom")), false);
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.errors.generic);
  });
});
