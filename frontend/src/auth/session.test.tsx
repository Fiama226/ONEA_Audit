import { act, cleanup, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { capturedHandler, fakeUser, mockOidc, renderApp, serveMe } from "@/test/auth";
import { safeReturnPath } from "./safePath";

describe("expiration de session", () => {
  it.each([
    ["accessTokenExpired", (o: ReturnType<typeof mockOidc>) => o.events.addAccessTokenExpired],
    ["silentRenewError", (o: ReturnType<typeof mockOidc>) => o.events.addSilentRenewError],
  ])("%s -> anonyme avec message de session expirée", async (_name, pick) => {
    serveMe();
    const oidc = mockOidc(fakeUser());
    const router = renderApp("/", oidc);
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();

    const handler = capturedHandler<[Error?]>(pick(oidc));
    await act(async () => {
      handler(new Error("boom"));
    });
    expect(await screen.findByText(fr.auth.sessionExpired)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(oidc.removeUser).toHaveBeenCalled();
  });

  it("se désabonne au démontage", async () => {
    serveMe();
    const oidc = mockOidc(fakeUser());
    renderApp("/", oidc);
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    cleanup();
    expect(oidc.events.removeAccessTokenExpired).toHaveBeenCalled();
    expect(oidc.events.removeSilentRenewError).toHaveBeenCalled();
  });
});

describe("chemin de retour", () => {
  it.each(["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)", "/\t/evil.com"])(
    "rejette %s",
    (bad) => {
      expect(safeReturnPath(bad)).toBe("/");
    },
  );

  it("conserve un chemin relatif valide", () => {
    expect(safeReturnPath("/missions?x=1")).toBe("/missions?x=1");
  });

  it("le callback ignore un returnTo malveillant", async () => {
    serveMe();
    const oidc = mockOidc(null);
    oidc.signinRedirectCallback = async () => fakeUser({ state: { returnTo: "//evil.com" } });
    const router = renderApp("/callback", oidc);
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("la page de connexion ignore un from malveillant", async () => {
    const oidc = mockOidc(null);
    renderApp({ pathname: "/connexion", state: { from: "/\\evil.com" } }, oidc);
    const btn = await screen.findByRole("button", { name: fr.auth.login });
    await act(async () => btn.click());
    const arg = (oidc.signinRedirect as unknown as { mock: { calls: { state: unknown }[][] } }).mock
      .calls[0]?.[0];
    expect(arg).toEqual({ state: { returnTo: "/" } });
  });
});
