import { screen } from "@testing-library/react";
import { http } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp, serveSession, unauthorized } from "@/test/auth";
import { server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

describe("RequireAuth", () => {
  it("redirige un anonyme vers /connexion", async () => {
    server.use(http.get(`${AUTH_URL}/session/`, () => unauthorized()));
    const { router } = renderApp("/missions");
    expect(await screen.findByRole("button", { name: fr.auth.login })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(router.state.location.state).toEqual({ from: "/missions" });
  });

  it("garde la requête et le fragment dans le chemin de retour", async () => {
    server.use(http.get(`${AUTH_URL}/session/`, () => unauthorized()));
    const { router } = renderApp("/missions?statut=EN_COURS#liste");
    expect(await screen.findByRole("button", { name: fr.auth.login })).toBeInTheDocument();
    expect(router.state.location.state).toEqual({ from: "/missions?statut=EN_COURS#liste" });
  });

  it("affiche la page protégée pour un utilisateur authentifié", async () => {
    serveSession();
    const { router } = renderApp("/");
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("impose le changement de mot de passe quand l'étape l'exige", async () => {
    serveSession(fakeMe(), "CHANGER_MOT_DE_PASSE");
    const { router } = renderApp("/missions");
    expect(await screen.findByRole("heading", { name: fr.auth.changeTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/mot-de-passe/changer");
    expect(screen.queryByRole("heading", { name: fr.nav.missions })).not.toBeInTheDocument();
  });

  it("laisse un utilisateur à jour ouvrir le changement volontaire", async () => {
    serveSession();
    const { router } = renderApp("/mot-de-passe/changer");
    expect(await screen.findByRole("heading", { name: fr.auth.changeTitle })).toBeInTheDocument();
    expect(screen.getByText(fr.auth.changeIntro)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/mot-de-passe/changer");
  });

  it("protège aussi la page de changement : anonyme renvoyé à la connexion", async () => {
    const { router } = renderApp("/mot-de-passe/changer");
    expect(await screen.findByRole("button", { name: fr.auth.login })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
  });
});
