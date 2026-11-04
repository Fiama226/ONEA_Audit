import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { aReport } from "../testUtils";
import { ImportCsvDialog } from "./ImportCsvDialog";

const URL_CSV = `${API_URL}/api/v1/user-accounts/import-csv/`;

function renderDialog() {
  return renderWithAuth(<ImportCsvDialog open onOpenChange={() => {}} />, "ADMIN");
}

const file = (name = "comptes.csv") => new File(["identifiant\na.b\n"], name, { type: "text/csv" });

async function choose(f = file()) {
  await userEvent.upload(screen.getByLabelText("Fichier CSV"), f);
}

describe("ImportCsvDialog", () => {
  it("explains the format and the ADMIN restriction", () => {
    renderDialog();
    expect(screen.getByText(/UTF-8, 300 lignes au plus/)).toBeInTheDocument();
    expect(
      screen.getByText(/Le rôle ADMIN ne peut pas être attribué par fichier/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importer" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Vérifier le fichier" })).toBeDisabled();
  });

  it("keeps Importer disabled until the same file was verified, then imports", async () => {
    const sent: string[] = [];
    server.use(
      http.post(URL_CSV, async ({ request }) => {
        const form = await request.formData();
        const dry = String(form.get("dry_run"));
        sent.push(dry);
        return HttpResponse.json(aReport({ dry_run: dry === "true" }));
      }),
    );
    renderDialog();
    await choose();
    expect(screen.getByRole("button", { name: "Importer" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    expect(
      await screen.findByText("Vérification — aucun compte n'a encore été créé"),
    ).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /chef/ })).toHaveTextContent(
      "3chefLe rôle ADMIN ne s'attribue que dans l'annuaire (Keycloak).",
    );
    expect(sent).toEqual(["true"]);
    expect(screen.getByRole("button", { name: "Importer" })).toBeEnabled();

    // Changer de fichier invalide la vérification.
    await choose(file("autre.csv"));
    expect(screen.getByRole("button", { name: "Importer" })).toBeDisabled();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    await screen.findByText("Vérification — aucun compte n'a encore été créé");
    expect(screen.getByRole("button", { name: "Importer" })).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: "Importer" }));
    expect(await screen.findByText("Import terminé")).toBeInTheDocument();
    expect(sent).toEqual(["true", "true", "false"]);
  });

  it("shows a 400 error in the dialog and does not enable Importer", async () => {
    server.use(
      http.post(URL_CSV, () =>
        HttpResponse.json({ detail: "Le fichier doit être encodé en UTF-8." }, { status: 400 }),
      ),
    );
    renderDialog();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le fichier doit être encodé en UTF-8.",
    );
    expect(screen.getByRole("button", { name: "Importer" })).toBeDisabled();
  });

  it("has no axe violation, report displayed", async () => {
    server.use(http.post(URL_CSV, () => HttpResponse.json(aReport())));
    renderDialog();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    await screen.findByRole("table");
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("rejects a file over 1 MB before any upload", async () => {
    let calls = 0;
    server.use(
      http.post(URL_CSV, () => {
        calls += 1;
        return HttpResponse.json(aReport());
      }),
    );
    renderDialog();
    const big = new File([new Uint8Array(1024 * 1024 + 1)], "gros.csv", { type: "text/csv" });
    await choose(big);
    expect(screen.getByRole("alert")).toHaveTextContent("Le fichier dépasse 1 Mo.");
    expect(screen.getByRole("button", { name: "Vérifier le fichier" })).toBeDisabled();
    expect(calls).toBe(0);
  });

  it("disables the file input while the check runs", async () => {
    server.use(
      http.post(URL_CSV, async () => {
        await new Promise((r) => setTimeout(r, 300));
        return HttpResponse.json(aReport());
      }),
    );
    renderDialog();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    expect(screen.getByLabelText("Fichier CSV")).toBeDisabled();
    await screen.findByRole("table");
    expect(screen.getByLabelText("Fichier CSV")).toBeEnabled();
  });
});
