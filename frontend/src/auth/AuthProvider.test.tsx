import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { apiFetch, resetCsrfToken } from "@/api/client";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp, serveSession, unauthorized } from "@/test/auth";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";
import { AuthProvider } from "./AuthProvider";
import { hasPendingLogout, markPendingLogout } from "./crossTab";
import { useAuth } from "./useAuth";

allowSlowShell();

function Probe() {
  const { status, me, etape } = useAuth();
  return (
    <p>
      status={status} user={me?.username ?? "-"} etape={etape ?? "-"}
    </p>
  );
}

describe("AuthProvider : sonde de session", () => {
  it("401 sur /auth/session/ : anonyme, sans page d'erreur", async () => {
    server.use(http.get(`${AUTH_URL}/session/`, () => unauthorized()));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(await screen.findByText(/status=anonymous user=-/)).toBeInTheDocument();
  });

  it("200 : authentifié avec le profil et l'étape", async () => {
    serveSession(fakeMe({ username: "auditeur1" }), "CHANGER_MOT_DE_PASSE");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(
      await screen.findByText(/status=authenticated user=auditeur1 etape=CHANGER_MOT_DE_PASSE/),
    ).toBeInTheDocument();
  });

  it("envoie le cookie de session (credentials: include) et aucun en-tête Authorization", async () => {
    // MSW ne transmet pas `credentials` : on lit l'appel à fetch lui-même.
    const spy = vi.spyOn(globalThis, "fetch");
    let authorization: string | null = "unset";
    server.use(
      http.get(`${AUTH_URL}/session/`, ({ request }) => {
        authorization = request.headers.get("Authorization");
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(await screen.findByText(/status=authenticated/)).toBeInTheDocument();
    const call = spy.mock.calls.find(([url]) => String(url).endsWith("/api/v1/auth/session/"));
    spy.mockRestore();
    expect(call?.[1]?.credentials).toBe("include");
    expect(authorization).toBeNull();
  });
});

describe("AuthProvider : session expirée en cours d'utilisation", () => {
  it("un 401 de l'API ramène à /connexion avec le message de session expirée", async () => {
    serveSession();
    const { router, client } = renderApp("/");
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(screen.queryByText(fr.auth.sessionExpired)).not.toBeInTheDocument();
    client.setQueryData(["donnees-precedentes"], { secret: true });

    server.use(
      http.get(`${AUTH_URL}/session/`, () => unauthorized()),
      http.get(`${API_URL}/api/v1/ressource/`, () => unauthorized("Session expirée.")),
    );
    await act(async () => {
      await apiFetch("/api/v1/ressource/").catch(() => undefined);
    });
    expect(await screen.findByText(fr.auth.sessionExpired)).toHaveAttribute("role", "alert");
    expect(router.state.location.pathname).toBe("/connexion");
    expect(client.getQueryData(["donnees-precedentes"])).toBeUndefined();
  });

  it("un 401 de la connexion elle-même n'est pas une session expirée", async () => {
    server.use(http.post(`${AUTH_URL}/login/`, () => unauthorized()));
    renderApp("/connexion");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(fr.auth.identifiant), "rai");
    await user.type(screen.getByLabelText(fr.auth.password), "mauvais");
    await user.click(screen.getByRole("button", { name: fr.auth.login }));
    expect(await screen.findByText(fr.auth.loginFailed)).toBeInTheDocument();
    expect(screen.queryByText(fr.auth.sessionExpired)).not.toBeInTheDocument();
  });
});

describe("AuthProvider : jeton CSRF", () => {
  it("redemande le jeton après la connexion (le serveur le renouvelle)", async () => {
    let emis = 0;
    const recus: Record<string, string | null> = {};
    server.use(
      http.get(`${AUTH_URL}/csrf/`, () => {
        emis += 1;
        return HttpResponse.json({ csrf_token: `csrf-${emis}` });
      }),
      http.post(`${AUTH_URL}/login/`, ({ request }) => {
        recus.login = request.headers.get("X-CSRFToken");
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
      http.post(`${AUTH_URL}/logout/`, ({ request }) => {
        recus.logout = request.headers.get("X-CSRFToken");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    function Actions() {
      const { login, logout, status } = useAuth();
      return (
        <>
          <p>status={status}</p>
          <button onClick={() => void login("rai", "mot-de-passe-solide")}>entrer</button>
          <button onClick={() => void logout()}>sortir</button>
        </>
      );
    }
    render(
      <AuthProvider>
        <Actions />
      </AuthProvider>,
    );
    await screen.findByText("status=anonymous");
    await userEvent.click(screen.getByText("entrer"));
    await screen.findByText("status=authenticated");
    await userEvent.click(screen.getByText("sortir"));
    await screen.findByText("status=anonymous");
    expect(recus.login).toMatch(/^csrf-\d+$/);
    expect(recus.logout).toMatch(/^csrf-\d+$/);
    expect(recus.logout).not.toBe(recus.login);
  });
});

describe("AuthProvider : déconnexion", () => {
  async function cliquerDeconnexion() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: new RegExp(fr.shell.userMenu) }));
    await user.click(await screen.findByRole("menuitem", { name: fr.auth.logout }));
  }

  async function seDeconnecter() {
    serveSession();
    const app = renderApp("/");
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    await cliquerDeconnexion();
    return app;
  }

  it("déconnexion volontaire : la page quittée n'est pas reprise (pas de from)", async () => {
    server.use(http.post(`${AUTH_URL}/logout/`, () => new HttpResponse(null, { status: 204 })));
    serveSession();
    const { router } = renderApp("/mon-compte");
    await screen.findByRole("heading", { name: fr.tutoriel.accountTitle });
    await cliquerDeconnexion();
    expect(await screen.findByRole("heading", { name: fr.auth.loginTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(router.state.location.state).toBeFalsy();
  });

  it("ne bloque jamais : jeton CSRF sans réponse, déconnexion locale en 2 s", async () => {
    resetCsrfToken();
    let envois = 0;
    server.use(
      http.get(`${AUTH_URL}/csrf/`, async () => {
        await delay("infinite");
        return HttpResponse.json({ csrf_token: "jamais" });
      }),
      http.post(`${AUTH_URL}/logout/`, () => {
        envois += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { router } = await seDeconnecter();
    expect(await screen.findByRole("heading", { name: fr.auth.loginTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(envois).toBe(0);
  });

  it("appelle POST /auth/logout/ puis revient à la connexion, cache vidé", async () => {
    const logout = vi.fn(() => new HttpResponse(null, { status: 204 }));
    server.use(http.post(`${AUTH_URL}/logout/`, logout));
    const { router, client } = await seDeconnecter();
    expect(await screen.findByRole("heading", { name: fr.auth.loginTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(logout).toHaveBeenCalledTimes(1);
    expect(client.getQueryCache().getAll()).toEqual([]);
    expect(screen.queryByText(fr.auth.sessionExpired)).not.toBeInTheDocument();
  });

  it.each([
    ["l'API échoue", () => HttpResponse.json({}, { status: 500 })],
    ["l'API est injoignable", () => HttpResponse.error()],
  ])("déconnecte quand même si %s, en signalant la fin non confirmée", async (_cas, respond) => {
    server.use(http.post(`${AUTH_URL}/logout/`, respond));
    const { router } = await seDeconnecter();
    expect(await screen.findByRole("heading", { name: fr.auth.loginTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/connexion");
    expect(await screen.findByText(fr.auth.logoutUnconfirmed)).toHaveAttribute("role", "alert");
    expect(hasPendingLogout()).toBe(true);
  });

  it("envoie la déconnexion en keepalive (livrée même si la page se ferme)", async () => {
    server.use(http.post(`${AUTH_URL}/logout/`, () => new HttpResponse(null, { status: 204 })));
    const spy = vi.spyOn(globalThis, "fetch");
    await seDeconnecter();
    await screen.findByRole("heading", { name: fr.auth.loginTitle });
    const call = spy.mock.calls.find(([url]) => String(url).endsWith("/api/v1/auth/logout/"));
    spy.mockRestore();
    expect(call?.[1]?.keepalive).toBe(true);
    expect(hasPendingLogout()).toBe(false);
    expect(screen.queryByText(fr.auth.logoutUnconfirmed)).not.toBeInTheDocument();
  });
});

describe("AuthProvider : déconnexion non confirmée, rejouée au démarrage", () => {
  it("rejoue POST /auth/logout/ AVANT de sonder la session, puis retire la marque", async () => {
    markPendingLogout();
    const ordre: string[] = [];
    server.use(
      http.post(`${AUTH_URL}/logout/`, () => {
        ordre.push("logout");
        return new HttpResponse(null, { status: 204 });
      }),
      http.get(`${AUTH_URL}/session/`, () => {
        ordre.push("session");
        return unauthorized();
      }),
    );
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(await screen.findByText(/status=anonymous/)).toBeInTheDocument();
    expect(ordre).toEqual(["logout", "session"]);
    expect(hasPendingLogout()).toBe(false);
  });

  it("rejeu encore impossible : anonyme sans sonder la session (qui la prolongerait)", async () => {
    markPendingLogout();
    let sondes = 0;
    server.use(
      http.post(`${AUTH_URL}/logout/`, () => HttpResponse.error()),
      http.get(`${AUTH_URL}/session/`, () => {
        sondes += 1;
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    renderApp("/");
    expect(await screen.findByText(fr.auth.logoutUnconfirmed)).toBeInTheDocument();
    expect(sondes).toBe(0);
    expect(hasPendingLogout()).toBe(true);
  });

  it("une nouvelle connexion retire la marque (la nouvelle session remplace l'ancienne)", async () => {
    markPendingLogout();
    server.use(
      http.post(`${AUTH_URL}/logout/`, () => HttpResponse.error()),
      http.post(`${AUTH_URL}/login/`, () => HttpResponse.json({ etape: "OK", me: fakeMe() })),
    );
    renderApp("/connexion");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(fr.auth.identifiant), "rai");
    await user.type(screen.getByLabelText(fr.auth.password), "mot-de-passe-solide");
    await user.click(screen.getByRole("button", { name: fr.auth.login }));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(hasPendingLogout()).toBe(false);
  });
});

describe("AuthProvider : plusieurs onglets", () => {
  /** Message d'un autre onglet (autre identifiant d'émetteur). */
  function signalAutreOnglet(type: "login" | "logout") {
    const channel = new BroadcastChannel("onea-auth");
    channel.postMessage({ type, from: "autre-onglet" });
    channel.close();
  }

  it("déconnexion dans un autre onglet : celui-ci revient à la connexion", async () => {
    serveSession();
    const { router } = renderApp("/");
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    signalAutreOnglet("logout");
    expect(await screen.findByRole("heading", { name: fr.auth.loginTitle })).toBeInTheDocument();
    expect(router.state.location.state).toBeFalsy();
  });

  it("connexion d'un autre agent dans un autre onglet : écran quitté, message affiché", async () => {
    serveSession(fakeMe({ id: 1 }));
    const { client } = renderApp("/");
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    client.setQueryData(["donnees-de-a"], { secret: true });
    serveSession(fakeMe({ id: 2, username: "autre" }));
    signalAutreOnglet("login");
    expect(await screen.findByText(fr.auth.sessionChanged)).toHaveAttribute("role", "alert");
    expect(client.getQueryData(["donnees-de-a"])).toBeUndefined();
  });

  it("connexion dans un autre onglet alors que celui-ci est anonyme : session reprise", async () => {
    renderApp("/connexion");
    await screen.findByRole("heading", { name: fr.auth.loginTitle });
    serveSession();
    signalAutreOnglet("login");
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
  });

  it("rejeu CSRF découvrant un autre agent : retour à la connexion avec le message", async () => {
    serveSession(fakeMe({ id: 1 }));
    renderApp("/");
    await screen.findByRole("heading", { name: fr.dashboard.raiTitle });
    let ecritures = 0;
    server.use(
      http.get(`${AUTH_URL}/session/`, () =>
        HttpResponse.json({ etape: "OK", me: fakeMe({ id: 2 }) }),
      ),
      http.post(`${API_URL}/api/v1/ressource/`, () => {
        ecritures += 1;
        return HttpResponse.json(
          { detail: "Jeton CSRF absent ou invalide : rechargez la page.", errors: {} },
          { status: 403 },
        );
      }),
    );
    await act(async () => {
      await apiFetch("/api/v1/ressource/", { method: "POST", json: {} }).catch(() => undefined);
    });
    expect(await screen.findByText(fr.auth.sessionChanged)).toBeInTheDocument();
    expect(ecritures).toBe(1);
  });
});
