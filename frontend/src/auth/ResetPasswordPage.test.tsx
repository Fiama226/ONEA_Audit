import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, renderApp } from "@/test/auth";
import { server, TEST_CSRF } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

const T = fr.auth;

async function ouvrir(state?: unknown) {
  const app = renderApp({ pathname: "/mot-de-passe/reinitialiser", state });
  expect(await screen.findByRole("heading", { name: T.resetTitle })).toBeInTheDocument();
  return { ...app, user: userEvent.setup() };
}

async function remplir(user: ReturnType<typeof userEvent.setup>, code: string, mdp: string) {
  await user.type(screen.getByLabelText(T.otpCode), code);
  await user.type(screen.getByLabelText(T.newPassword), mdp);
  await user.type(screen.getByLabelText(T.confirmPassword), mdp);
  await user.click(screen.getByRole("button", { name: T.resetSubmit }));
}

describe("ResetPasswordPage", () => {
  it("affiche la règle des 12 caractères et reprend l'identifiant saisi", async () => {
    await ouvrir({ identifiant: "agent@onea.bf" });
    expect(screen.getByLabelText(T.identifiant)).toHaveValue("agent@onea.bf");
    expect(screen.getByLabelText(T.newPassword)).toHaveAccessibleDescription(T.passwordRule);
  });

  it("succès : envoie les champs avec CSRF puis renvoie à la connexion avec un message", async () => {
    let body: unknown = null;
    let csrf: string | null = null;
    server.use(
      http.post(`${AUTH_URL}/password/reset/`, async ({ request }) => {
        body = await request.json();
        csrf = request.headers.get("X-CSRFToken");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { router, user } = await ouvrir({ identifiant: "agent@onea.bf" });
    await remplir(user, "123456", "un-nouveau-solide");
    expect(await screen.findByText(T.passwordResetDone)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(body).toEqual({
      identifiant: "agent@onea.bf",
      code: "123456",
      nouveau_mot_de_passe: "un-nouveau-solide",
    });
    expect(csrf).toBe(TEST_CSRF);
  });

  it("code refusé : message lié au champ du code, focus", async () => {
    server.use(
      http.post(`${AUTH_URL}/password/reset/`, () =>
        HttpResponse.json({ detail: "Code invalide ou expiré.", errors: {} }, { status: 400 }),
      ),
    );
    const { user } = await ouvrir({ identifiant: "agent@onea.bf" });
    await remplir(user, "000000", "un-nouveau-solide");
    const code = screen.getByLabelText(T.otpCode);
    await waitFor(() => expect(code).toHaveFocus());
    expect(code).toHaveAccessibleDescription(`${T.otpHelp} ${T.otpInvalid}`);
  });

  it("mot de passe refusé par le serveur : message sous le nouveau mot de passe", async () => {
    server.use(
      http.post(`${AUTH_URL}/password/reset/`, () =>
        HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { nouveau_mot_de_passe: ["Ce mot de passe est trop courant."] },
          },
          { status: 400 },
        ),
      ),
    );
    const { user } = await ouvrir({ identifiant: "agent@onea.bf" });
    await remplir(user, "123456", "motdepasse123");
    const champ = screen.getByLabelText(T.newPassword);
    await waitFor(() => expect(champ).toHaveFocus());
    expect(champ).toHaveAccessibleDescription(
      `${T.passwordRule} Ce mot de passe est trop courant.`,
    );
  });

  it("mot de passe trop court : refusé avant envoi", async () => {
    const { user } = await ouvrir({ identifiant: "agent@onea.bf" });
    await remplir(user, "123456", "court");
    expect(await screen.findByText(T.passwordTooShort)).toBeInTheDocument();
  });
});
