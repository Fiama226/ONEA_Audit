import { act, render, screen } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, serveSession } from "@/test/auth";
import { server } from "@/test/msw";
import { AuthProvider } from "./AuthProvider";
import { RequireRole } from "./RequireRole";
import { useAuth } from "./useAuth";

function wrap(children: ReactNode) {
  render(<AuthProvider>{children}</AuthProvider>);
}

const secret = <RequireRole roles={["RAI", "AUDITE"]}>contenu secret</RequireRole>;

describe("RequireRole hors RequireAuth", () => {
  it("ne rend jamais le contenu pour un anonyme", async () => {
    wrap(secret);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
    expect(screen.queryByText(fr.errors.forbidden)).not.toBeInTheDocument();
  });

  it("affiche le chargement et pas le contenu pendant loading", () => {
    server.use(
      http.get(`${AUTH_URL}/session/`, async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );
    wrap(secret);
    expect(screen.getByText(fr.common.loading)).toBeInTheDocument();
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });

  it("ne rend jamais le contenu en statut error", async () => {
    server.use(http.get(`${AUTH_URL}/session/`, () => HttpResponse.error()));
    wrap(secret);
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });

  it("masque le contenu protégé pendant la déconnexion", async () => {
    serveSession();
    server.use(http.post(`${AUTH_URL}/logout/`, () => new HttpResponse(null, { status: 204 })));
    function Logout() {
      const { logout } = useAuth();
      return <button onClick={() => void logout()}>sortir</button>;
    }
    wrap(
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
