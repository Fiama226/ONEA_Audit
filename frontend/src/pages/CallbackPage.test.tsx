import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { fakeUser, mockOidc, renderApp, serveMe } from "@/test/auth";

describe("CallbackPage", () => {
  it("redirige vers le chemin mémorisé", async () => {
    serveMe();
    const oidc = mockOidc(null);
    oidc.signinRedirectCallback = async () => fakeUser({ state: { returnTo: "/missions" } });
    const router = renderApp("/callback", oidc);
    expect(await screen.findByText(fr.errors.notFound)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/missions");
  });

  it("redirige vers / par défaut", async () => {
    serveMe();
    const oidc = mockOidc(null);
    oidc.signinRedirectCallback = async () => fakeUser();
    const router = renderApp("/callback", oidc);
    expect(await screen.findByText(fr.app.tagline)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });
});
