import { act, cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { capturedHandler, fakeUser, mockOidc, renderApp, serveMe } from "@/test/auth";
import { safeReturnPath } from "./safePath";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

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

describe("fin de session", () => {
  async function seDeconnecter(oidc: ReturnType<typeof mockOidc>) {
    renderApp("/", oidc);
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: new RegExp(fr.shell.userMenu) }));
    await user.click(await screen.findByRole("menuitem", { name: fr.auth.logout }));
  }

  it("appelle l'API de fin de session avec le jeton puis signoutRedirect", async () => {
    serveMe();
    const ordre: string[] = [];
    let autorisation: string | null = null;
    server.use(
      http.post(`${API_URL}/api/v1/session/fin/`, ({ request }) => {
        autorisation = request.headers.get("Authorization");
        ordre.push("api");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const oidc = mockOidc(fakeUser());
    (
      oidc.signoutRedirect as unknown as { mockImplementation: (f: () => Promise<void>) => void }
    ).mockImplementation(async () => {
      ordre.push("signout");
    });
    await seDeconnecter(oidc);
    await vi.waitFor(() => expect(oidc.signoutRedirect).toHaveBeenCalled());
    expect(ordre).toEqual(["api", "signout"]);
    expect(autorisation).toBe("Bearer tok-123");
  });

  it("déconnecte quand même si l'API échoue", async () => {
    serveMe();
    server.use(
      http.post(`${API_URL}/api/v1/session/fin/`, () => HttpResponse.json({}, { status: 500 })),
    );
    const oidc = mockOidc(fakeUser());
    await seDeconnecter(oidc);
    await vi.waitFor(() => expect(oidc.signoutRedirect).toHaveBeenCalled());
  });

  it("déconnecte quand même si l'API est injoignable", async () => {
    serveMe();
    server.use(http.post(`${API_URL}/api/v1/session/fin/`, () => HttpResponse.error()));
    const oidc = mockOidc(fakeUser());
    await seDeconnecter(oidc);
    await vi.waitFor(() => expect(oidc.signoutRedirect).toHaveBeenCalled());
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
