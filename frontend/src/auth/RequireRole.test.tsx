import { act, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { apiFetch } from "@/api/client";
import { fr } from "@/i18n/fr";
import { capturedHandler, fakeUser, mockOidc, serveMe } from "@/test/auth";
import { API_URL, server } from "@/test/msw";
import type { OidcUser } from "./oidc";
import { AuthProvider } from "./AuthProvider";
import { RequireRole } from "./RequireRole";
import { useAuth } from "./useAuth";

function wrap(oidc: ReturnType<typeof mockOidc>, children: ReactNode) {
  render(<AuthProvider userManager={oidc}>{children}</AuthProvider>);
}

const secret = <RequireRole roles={["RAI", "AUDITE"]}>contenu secret</RequireRole>;

describe("RequireRole hors RequireAuth", () => {
  it("ne rend jamais le contenu pour un anonyme", async () => {
    wrap(mockOidc(null), secret);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
    expect(screen.queryByText(fr.errors.forbidden)).not.toBeInTheDocument();
  });

  it("affiche le chargement et pas le contenu pendant loading", () => {
    const oidc = mockOidc(null);
    oidc.getUser = () => new Promise(() => {});
    wrap(oidc, secret);
    expect(screen.getByText(fr.common.loading)).toBeInTheDocument();
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });

  it("ne rend jamais le contenu en statut error", async () => {
    server.use(http.get(`${API_URL}/api/v1/me/`, () => HttpResponse.error()));
    wrap(mockOidc(fakeUser()), secret);
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });

  it("masque le contenu protégé pendant la déconnexion", async () => {
    serveMe();
    function Logout() {
      const { logout } = useAuth();
      return <button onClick={() => void logout()}>sortir</button>;
    }
    wrap(
      mockOidc(fakeUser()),
      <>
        {secret}
        <Logout />
      </>,
    );
    expect(await screen.findByText("contenu secret")).toBeInTheDocument();
    await act(async () => {
      screen.getByText("sortir").click();
    });
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });
});

describe("jeton porteur", () => {
  it("envoie le jeton renouvelé après addUserLoaded", async () => {
    serveMe();
    const oidc = mockOidc(fakeUser());
    let seen: string | null = null;
    function Probe() {
      const { status } = useAuth();
      return <p>{status}</p>;
    }
    wrap(oidc, <Probe />);
    expect(await screen.findByText("authenticated")).toBeInTheDocument();

    server.use(
      http.get(`${API_URL}/api/v1/me/`, ({ request }) => {
        seen = request.headers.get("Authorization");
        return HttpResponse.json({});
      }),
    );
    const onLoaded = capturedHandler<[OidcUser]>(oidc.events.addUserLoaded);
    onLoaded(fakeUser({ access_token: "tok-renewed" }));
    await apiFetch("/api/v1/me/");
    expect(seen).toBe("Bearer tok-renewed");
  });
});
