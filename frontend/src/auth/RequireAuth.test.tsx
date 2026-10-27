import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { fakeUser, mockOidc, renderApp, serveMe } from "@/test/auth";
import { API_URL, server } from "@/test/msw";

describe("RequireAuth", () => {
  it("redirige un anonyme vers /connexion", async () => {
    const router = renderApp("/missions", mockOidc(null));
    expect(await screen.findByRole("button", { name: fr.auth.login })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
  });

  it("affiche la page protégée pour un utilisateur authentifié", async () => {
    serveMe();
    const router = renderApp("/", mockOidc(fakeUser()));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("repasse en anonyme quand /me répond 401 avec un jeton", async () => {
    server.use(http.get(`${API_URL}/api/v1/me/`, () => HttpResponse.json({}, { status: 401 })));
    const oidc = mockOidc(fakeUser());
    const router = renderApp("/", oidc);
    expect(await screen.findByRole("button", { name: fr.auth.login })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(oidc.removeUser).toHaveBeenCalled();
  });
});
