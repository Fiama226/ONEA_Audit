import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, onTestFinished, vi } from "vitest";
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
    expect(screen.getByText(/UTF-8, 1 000 lignes au plus/)).toBeInTheDocument();
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
      "3chefLe rôle Administrateur ne peut pas être attribué par import.",
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

  it("sends the welcome email option, checked by default", async () => {
    const sent: [string, string][] = [];
    server.use(
      http.post(URL_CSV, async ({ request }) => {
        const form = await request.formData();
        sent.push([String(form.get("dry_run")), String(form.get("envoyer_courriel"))]);
        return HttpResponse.json(aReport({ dry_run: form.get("dry_run") === "true" }));
      }),
    );
    const user = userEvent.setup();
    renderDialog();
    const option = screen.getByRole("checkbox", {
      name: "Envoyer le courriel de bienvenue à chaque compte créé",
    });
    expect(option).toBeChecked();
    expect(option).toHaveAccessibleDescription(/télécharger une seule fois/);
    await choose();
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    await screen.findByText("Vérification — aucun compte n'a encore été créé");
    await user.click(option);
    await user.click(screen.getByRole("button", { name: "Importer" }));
    await screen.findByText("Import terminé");
    expect(sent).toEqual([
      ["true", "true"],
      ["false", "false"],
    ]);
  });

  it("downloads the password file once, then says it is gone", async () => {
    const ID = "3f2b8f0e-4c1a-4d6e-9a7b-1c2d3e4f5a6b";
    let downloads = 0;
    server.use(
      http.post(URL_CSV, async ({ request }) => {
        const dry = (await request.formData()).get("dry_run") === "true";
        return HttpResponse.json(
          aReport({ dry_run: dry, fichier_mots_de_passe_id: dry ? null : ID }),
        );
      }),
      http.get(`${API_URL}/api/v1/user-accounts/import-passwords/${ID}/`, () => {
        downloads += 1;
        if (downloads > 1) {
          return HttpResponse.json({ detail: "Introuvable.", errors: {} }, { status: 404 });
        }
        return new HttpResponse("identifiant;mot_de_passe\na.b;Tmp-1\n", {
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="mots-de-passe-temporaires.csv"',
          },
        });
      }),
    );
    const { createObjectURL, revokeObjectURL } = URL;
    const createUrl = vi.fn(() => "blob:mots-de-passe");
    URL.createObjectURL = createUrl;
    URL.revokeObjectURL = vi.fn();
    onTestFinished(() => {
      URL.createObjectURL = createObjectURL;
      URL.revokeObjectURL = revokeObjectURL;
    });
    const user = userEvent.setup();
    renderDialog();
    await choose();
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    await screen.findByText("Vérification — aucun compte n'a encore été créé");
    expect(
      screen.queryByRole("button", { name: "Télécharger le fichier des mots de passe" }),
    ).toBeNull();
    await user.click(screen.getByRole("button", { name: "Importer" }));
    await screen.findByText("Import terminé");

    expect(screen.getByText(/ne peut être téléchargé qu'une seule fois/)).toBeVisible();
    const download = screen.getByRole("button", {
      name: "Télécharger le fichier des mots de passe",
    });
    await user.click(download);
    expect(await screen.findByText(/Fichier téléchargé/)).toBeVisible();
    expect(createUrl).toHaveBeenCalledTimes(1);
    expect(downloads).toBe(1);
    // Téléchargé une fois : le bouton disparaît, plus aucun appel n'est possible.
    expect(
      screen.queryByRole("button", { name: "Télécharger le fichier des mots de passe" }),
    ).toBeNull();
  });

  it("explains that the password file is gone on a 404", async () => {
    const ID = "3f2b8f0e-4c1a-4d6e-9a7b-1c2d3e4f5a6b";
    server.use(
      http.post(URL_CSV, async ({ request }) => {
        const dry = (await request.formData()).get("dry_run") === "true";
        return HttpResponse.json(
          aReport({ dry_run: dry, fichier_mots_de_passe_id: dry ? null : ID }),
        );
      }),
      http.get(`${API_URL}/api/v1/user-accounts/import-passwords/${ID}/`, () =>
        HttpResponse.json({ detail: "Introuvable.", errors: {} }, { status: 404 }),
      ),
    );
    const user = userEvent.setup();
    renderDialog();
    await choose();
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    await screen.findByText("Vérification — aucun compte n'a encore été créé");
    await user.click(screen.getByRole("button", { name: "Importer" }));
    await user.click(
      await screen.findByRole("button", { name: "Télécharger le fichier des mots de passe" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/Ce fichier n'est plus disponible/);
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
