import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import * as upload from "@/api/upload";
import { EvidenceUploader } from "./EvidenceUploader";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <EvidenceUploader ficheId="f1" missionId="m1" />
    </QueryClientProvider>,
  );
}

describe("EvidenceUploader", () => {
  it("exige un fichier puis un libellé et ne contacte pas le serveur", async () => {
    const spy = vi.spyOn(upload, "uploadWithProgress");
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "Déposer la pièce" }));
    expect(await screen.findByText("Choisissez un fichier.")).toBeVisible();
    await user.upload(
      screen.getByLabelText("Fichier à déposer"),
      new File(["x"], "p.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Déposer la pièce" }));
    expect(await screen.findByText("Le libellé est obligatoire.")).toBeVisible();
    expect(screen.getByLabelText("Libellé de la pièce")).toHaveFocus();
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("annonce la progression, puis vide le formulaire", async () => {
    let finish: () => void = () => {};
    const spy = vi
      .spyOn(upload, "uploadWithProgress")
      .mockImplementation((_url, _form, onProgress) => {
        onProgress(0.4);
        return new Promise((resolve) => {
          finish = () => resolve({} as never);
        });
      });
    const user = userEvent.setup();
    setup();
    await user.upload(
      screen.getByLabelText("Fichier à déposer"),
      new File(["x"], "p.pdf", { type: "application/pdf" }),
    );
    await user.type(screen.getByLabelText("Libellé de la pièce"), "Facture 12");
    await user.click(screen.getByRole("button", { name: "Déposer la pièce" }));
    const bar = await screen.findByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByRole("button", { name: "Annuler l'envoi" })).toBeVisible();
    finish();
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Libellé de la pièce")).toHaveValue("");
    spy.mockRestore();
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup();
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
