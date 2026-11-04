import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp, serveSession } from "@/test/auth";
import { server, TEST_CSRF } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

const T = fr.auth;

async function ouvrirChangementImpose() {
  serveSession(fakeMe(), "CHANGER_MOT_DE_PASSE");
  const app = renderApp("/");
  expect(await screen.findByRole("heading", { name: T.changeTitle })).toBeInTheDocument();
  return { ...app, user: userEvent.setup() };
}

async function remplir(
  user: ReturnType<typeof userEvent.setup>,
  ancien: string,
  nouveau: string,
  confirmation = nouveau,
) {
  if (ancien) await user.type(screen.getByLabelText(T.currentPassword), ancien);
  if (nouveau) await user.type(screen.getByLabelText(T.newPassword), nouveau);
  if (confirmation) await user.type(screen.getByLabelText(T.confirmPassword), confirmation);
  await user.click(screen.getByRole("button", { name: T.changeSubmit }));
}

describe("ChangePasswordPage", () => {
  it("affiche la règle des 12 caractères, reliée au champ du nouveau mot de passe", async () => {
    await ouvrirChangementImpose();
    expect(screen.getByText(T.changeForcedIntro)).toBeInTheDocument();
    const nouveau = screen.getByLabelText(T.newPassword);
    expect(nouveau).toHaveAccessibleDescription(T.passwordRule);
    expect(nouveau).toHaveAttribute("autocomplete", "new-password");
    expect(T.passwordRule).toMatch(/12 caractères/);
  });

  it("refuse un mot de passe trop court, sans appel au serveur, avec focus", async () => {
    let calls = 0;
    server.use(
      http.post(`${AUTH_URL}/password/change/`, () => {
        calls += 1;
        return HttpResponse.json({});
      }),
    );
    const { user } = await ouvrirChangementImpose();
    await remplir(user, "temporaire-123", "court");
    const nouveau = screen.getByLabelText(T.newPassword);
    await waitFor(() => expect(nouveau).toHaveFocus());
    expect(nouveau).toHaveAccessibleDescription(`${T.passwordRule} ${T.passwordTooShort}`);
    expect(calls).toBe(0);
  });

  it("refuse une confirmation différente", async () => {
    const { user } = await ouvrirChangementImpose();
    await remplir(user, "temporaire-123", "un-nouveau-solide", "un-autre-solide!");
    expect(await screen.findByText(T.passwordMismatch)).toBeInTheDocument();
    expect(screen.getByLabelText(T.confirmPassword)).toHaveAttribute("aria-invalid", "true");
  });

  it("affiche l'erreur du serveur sous le mot de passe actuel", async () => {
    server.use(
      http.post(`${AUTH_URL}/password/change/`, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { ancien: ["Mot de passe actuel incorrect."] } },
          { status: 400 },
        ),
      ),
    );
    const { user } = await ouvrirChangementImpose();
    await remplir(user, "faux-mot-de-passe", "un-nouveau-solide");
    const ancien = screen.getByLabelText(T.currentPassword);
    await waitFor(() => expect(ancien).toHaveFocus());
    expect(ancien).toHaveAccessibleDescription(
      `${T.currentPasswordTemporaryHelp} Mot de passe actuel incorrect.`,
    );
  });

  it("succès : envoie ancien/nouveau avec CSRF puis ouvre l'application", async () => {
    let body: unknown = null;
    let csrf: string | null = null;
    server.use(
      http.post(`${AUTH_URL}/password/change/`, async ({ request }) => {
        body = await request.json();
        csrf = request.headers.get("X-CSRFToken");
        serveSession();
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    const { router, user } = await ouvrirChangementImpose();
    await remplir(user, "temporaire-123", "un-nouveau-solide");
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(body).toEqual({ ancien: "temporaire-123", nouveau: "un-nouveau-solide" });
    expect(csrf).toBe(TEST_CSRF);
  });

  it("changement volontaire : retour à Mon compte avec une confirmation (message d'état)", async () => {
    server.use(
      http.post(`${AUTH_URL}/password/change/`, () =>
        HttpResponse.json({ etape: "OK", me: fakeMe() }),
      ),
    );
    serveSession();
    const { router } = renderApp({
      pathname: "/mot-de-passe/changer",
      state: { from: "/mon-compte" },
    });
    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: T.changeTitle })).toBeInTheDocument();
    // Le lien d'abandon ramène aussi à la page d'origine.
    expect(screen.getByRole("link", { name: T.changeCancel })).toHaveAttribute(
      "href",
      "/mon-compte",
    );
    await remplir(user, "ancien-mot-de-passe", "un-nouveau-solide");
    expect(await screen.findByText(T.passwordChanged)).toHaveAttribute("role", "status");
    expect(router.state.location.pathname).toBe("/mon-compte");
  });

  it("rend la page dans le repère principal #contenu (lien d'évitement, e2e)", async () => {
    await ouvrirChangementImpose();
    expect(screen.getByRole("main")).toHaveAttribute("id", "contenu");
  });

  it("n'a pas de violation axe", async () => {
    await ouvrirChangementImpose();
    const opts = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe(document.body, opts)).violations).toEqual([]);
  });
});
