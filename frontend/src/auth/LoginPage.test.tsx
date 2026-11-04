import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp, serveSession, unauthorized } from "@/test/auth";
import { server, TEST_CSRF } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

const T = fr.auth;

async function fill(identifiant: string, motDePasse: string) {
  const user = userEvent.setup();
  const submit = await screen.findByRole("button", { name: T.login });
  if (identifiant) await user.type(screen.getByLabelText(T.identifiant), identifiant);
  if (motDePasse) await user.type(screen.getByLabelText(T.password), motDePasse);
  await user.click(submit);
  return user;
}

describe("LoginPage", () => {
  it("redirige un anonyme vers /connexion puis le ramène à la page demandée", async () => {
    let body: unknown = null;
    let csrf: string | null = null;
    server.use(
      http.post(`${AUTH_URL}/login/`, async ({ request }) => {
        body = await request.json();
        csrf = request.headers.get("X-CSRFToken");
        serveSession();
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    const { router } = renderApp("/missions");
    expect(await screen.findByRole("heading", { name: T.loginTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");

    await fill("rai", "mot-de-passe-solide");
    expect(await screen.findByRole("heading", { name: fr.nav.missions })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/missions");
    expect(body).toEqual({ identifiant: "rai", mot_de_passe: "mot-de-passe-solide" });
    expect(csrf).toBe(TEST_CSRF);
  });

  it("échec : message lié au champ (aria-describedby), focus, mot de passe effacé", async () => {
    server.use(
      http.post(`${AUTH_URL}/login/`, () => unauthorized("Identifiant ou mot de passe incorrect.")),
    );
    renderApp("/connexion");
    await fill("rai", "mauvais");

    const password = screen.getByLabelText(T.password);
    await waitFor(() => expect(password).toHaveFocus());
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(password).toHaveAccessibleDescription(T.loginFailed);
    expect(password).toHaveValue("");
    // L'identifiant est signalé par le même message (on ne dit pas lequel des deux est faux).
    expect(screen.getByLabelText(T.identifiant)).toHaveAccessibleDescription(T.loginFailed);
  });

  it.each([
    ["compte verrouillé", () => unauthorized("Compte verrouillé jusqu'à 10 h 15.")],
    ["compte désactivé", () => unauthorized("Compte désactivé.")],
    [
      "données invalides",
      () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { identifiant: ["Trop long."] } },
          { status: 400 },
        ),
    ],
  ])("%s : le message affiché reste le même", async (_cause, respond) => {
    server.use(http.post(`${AUTH_URL}/login/`, respond));
    renderApp("/connexion");
    await fill("rai", "mauvais");
    expect(await screen.findByText(T.loginFailed)).toBeInTheDocument();
    expect(screen.queryByText(/verrouillé|désactivé|Trop long/)).not.toBeInTheDocument();
  });

  it("champs vides : erreur liée au premier champ, qui reçoit le focus", async () => {
    renderApp("/connexion");
    await fill("", "");
    const identifiant = screen.getByLabelText(T.identifiant);
    await waitFor(() => expect(identifiant).toHaveFocus());
    expect(identifiant).toHaveAccessibleDescription(T.identifiantRequired);
    expect(screen.getByLabelText(T.password)).toHaveAccessibleDescription(T.passwordRequired);
  });

  it("serveur injoignable : message réseau, pas le message d'échec", async () => {
    server.use(http.post(`${AUTH_URL}/login/`, () => HttpResponse.error()));
    renderApp("/connexion");
    await fill("rai", "mot-de-passe-solide");
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.errors.network);
    expect(screen.queryByText(T.loginFailed)).not.toBeInTheDocument();
  });

  it("ignore un chemin de retour malveillant", async () => {
    server.use(
      http.post(`${AUTH_URL}/login/`, () => {
        serveSession();
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    const { router } = renderApp({ pathname: "/connexion", state: { from: "/\\evil.com" } });
    await fill("rai", "mot-de-passe-solide");
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("propose le lien « mot de passe oublié » et n'a pas de violation axe", async () => {
    renderApp("/connexion");
    const link = await screen.findByRole("link", { name: T.forgotLink });
    expect(link).toHaveAttribute("href", "/mot-de-passe-oublie");
    const opts = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe(document.body, opts)).violations).toEqual([]);
  });
});
