import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { AUTH_URL, fakeMe, renderApp, serveSession } from "@/test/auth";
import { server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";
import { TUTORIEL_VERSION } from "../etapes";

allowSlowShell();

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const SWITCH = "Demander un code par courriel à chaque connexion";
const VU = { version_vue: TUTORIEL_VERSION, termine_le: "2026-11-01T10:00:00Z" };

function openAccount(me: Record<string, unknown> = {}) {
  serveSession(fakeMe({ tutoriel: VU, ...me }));
  return renderApp("/mon-compte");
}

async function findSwitch() {
  return screen.findByRole("switch", { name: SWITCH });
}

describe("MonComptePage — mot de passe", () => {
  it("links to the password change page, from the page and from the user menu", async () => {
    const user = userEvent.setup();
    openAccount();
    const link = await screen.findByRole("link", { name: "Changer mon mot de passe" });
    expect(link).toHaveAttribute("href", "/mot-de-passe/changer");
    await user.click(screen.getByRole("button", { name: /Menu utilisateur/ }));
    expect(
      await screen.findByRole("menuitem", { name: "Changer mon mot de passe" }),
    ).toHaveAttribute("href", "/mot-de-passe/changer");
  });
});

describe("MonComptePage — code de connexion", () => {
  it("turns the login code on", async () => {
    let calls = 0;
    server.use(
      http.post(`${AUTH_URL}/otp/enable/`, () => {
        calls += 1;
        return HttpResponse.json({ otp_connexion_actif: true });
      }),
    );
    const user = userEvent.setup();
    openAccount();
    const toggle = await findSwitch();
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    await waitFor(() => expect(toggle).toBeChecked());
    expect(await screen.findByText(/Code de connexion activé/)).toBeVisible();
    expect(calls).toBe(1);
  });

  it("disables the switch with an explanation when email is not configured", async () => {
    server.use(
      http.post(`${AUTH_URL}/otp/enable/`, () =>
        HttpResponse.json(
          { detail: "Envoi de courriels non configuré", errors: {} },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    openAccount();
    const toggle = await findSwitch();
    // Régions annoncées présentes (vides) avant le refus : leur remplissage sera lu.
    const emptyStatuses = screen.getAllByRole("status").filter((el) => el.textContent === "");
    await user.click(toggle);
    await waitFor(() => expect(toggle).toBeDisabled());
    expect(toggle).not.toBeChecked();
    expect(toggle).toHaveAccessibleDescription(
      /L'envoi de courriels n'est pas configuré sur la plateforme/,
    );
    const explanation = screen.getByText(/L'envoi de courriels n'est pas configuré/);
    expect(explanation).toBeVisible();
    expect(emptyStatuses).toContain(explanation);
    // L'interrupteur désactivé a perdu le focus : il passe à l'explication.
    expect(explanation).toHaveFocus();
  });

  it("disables the switch upfront when the account has no email address", async () => {
    let calls = 0;
    server.use(
      http.post(`${AUTH_URL}/otp/enable/`, () => {
        calls += 1;
        return HttpResponse.json({ otp_connexion_actif: true });
      }),
    );
    openAccount({ email: "" });
    const toggle = await findSwitch();
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAccessibleDescription(/Aucune adresse de courriel n'est enregistrée/);
    expect(calls).toBe(0);
  });

  it("asks the current password to turn it off, errors tied to the field", async () => {
    const sent: unknown[] = [];
    server.use(
      http.post(`${AUTH_URL}/otp/disable/`, async ({ request }) => {
        const body = (await request.json()) as { mot_de_passe: string };
        sent.push(body);
        if (body.mot_de_passe !== "bon-mot-de-passe") {
          return HttpResponse.json(
            { detail: "Données invalides.", errors: { mot_de_passe: ["Mot de passe incorrect."] } },
            { status: 400 },
          );
        }
        return HttpResponse.json({ otp_connexion_actif: false });
      }),
    );
    const user = userEvent.setup();
    openAccount({ otp_connexion_actif: true });
    const toggle = await findSwitch();
    expect(toggle).toBeChecked();
    await user.click(toggle);
    const dialog = await screen.findByRole("dialog", { name: "Désactiver le code de connexion" });
    const password = within(dialog).getByLabelText("Mot de passe actuel");
    expect(password).toHaveFocus();
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);

    await user.click(within(dialog).getByRole("button", { name: "Désactiver le code" }));
    expect(await within(dialog).findByText("Saisissez votre mot de passe actuel.")).toBeVisible();
    expect(sent).toHaveLength(0);

    await user.type(password, "mauvais");
    await user.click(within(dialog).getByRole("button", { name: "Désactiver le code" }));
    expect(await within(dialog).findByText("Mot de passe incorrect.")).toBeVisible();
    expect(password).toHaveAccessibleDescription("Mot de passe incorrect.");

    await user.clear(password);
    await user.type(password, "bon-mot-de-passe");
    await user.click(within(dialog).getByRole("button", { name: "Désactiver le code" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(toggle).not.toBeChecked();
    expect(toggle).toHaveFocus();
    expect(screen.getByText("Code de connexion désactivé.")).toBeVisible();
  });

  it("keeps the code on when the password dialog is cancelled", async () => {
    const user = userEvent.setup();
    openAccount({ otp_connexion_actif: true });
    const toggle = await findSwitch();
    await user.click(toggle);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Annuler" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(toggle).toBeChecked();
    expect(toggle).toHaveFocus();
  });

  it("has no accessibility violation", async () => {
    openAccount();
    await findSwitch();
    const results = await axe(document.body, NO_CONTRAST);
    expect(results.violations).toEqual([]);
  });
});
