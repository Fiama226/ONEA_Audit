import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { AlertDialog, AlertDialogContent, AlertDialogTitle } from "./alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog";

function Controlled() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Ouvrir
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>Titre</DialogTitle>
          <DialogDescription>Description</DialogDescription>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ControlledAlert() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Ouvrir
      </button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogTitle>Titre</AlertDialogTitle>
          <button type="button" onClick={() => setOpen(false)}>
            Annuler
          </button>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

describe("retour du focus des boîtes de dialogue contrôlées", () => {
  it("rend le focus au bouton d'ouverture à la fermeture par Échap (Dialog)", async () => {
    render(<Controlled />);
    const bouton = screen.getByRole("button", { name: "Ouvrir" });
    await userEvent.click(bouton);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(bouton).toHaveFocus();
  });

  it("rend le focus au bouton d'ouverture (AlertDialog)", async () => {
    render(<ControlledAlert />);
    const bouton = screen.getByRole("button", { name: "Ouvrir" });
    await userEvent.click(bouton);
    await userEvent.click(await screen.findByRole("button", { name: "Annuler" }));
    expect(bouton).toHaveFocus();
  });
});
