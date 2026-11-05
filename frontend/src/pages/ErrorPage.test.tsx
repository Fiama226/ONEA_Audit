import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp } from "@/test/auth";
import { server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

describe("ErrorPage", () => {
  it("s'affiche si l'API est injoignable puis réessaie", async () => {
    server.use(http.get(`${AUTH_URL}/session/`, () => HttpResponse.error()));
    const { router } = renderApp("/");
    expect(await screen.findByText(fr.errors.unreachable)).toBeInTheDocument();

    server.use(
      http.get(`${AUTH_URL}/session/`, () => HttpResponse.json({ etape: "OK", me: fakeMe() })),
    );
    await userEvent.click(screen.getByRole("button", { name: fr.common.retry }));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });
});

describe("ErrorPage compte désactivé", () => {
  it("affiche le détail du serveur sur 403 sans retourner à la connexion", async () => {
    const detail = "Votre compte est désactivé.";
    server.use(
      http.get(`${AUTH_URL}/session/`, () => HttpResponse.json({ detail }, { status: 403 })),
    );
    const { router } = renderApp("/");
    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByText(fr.errors.accountDisabledTitle)).toBeInTheDocument();
    expect(router.state.location.pathname).not.toBe("/connexion");
  });
});
