import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { fakeMe, fakeUser, mockOidc, renderApp } from "@/test/auth";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

describe("ErrorPage", () => {
  it("s'affiche si l'API est injoignable puis réessaie", async () => {
    server.use(http.get(`${API_URL}/api/v1/me/`, () => HttpResponse.error()));
    const router = renderApp("/", mockOidc(fakeUser()));
    expect(await screen.findByText(fr.errors.unreachable)).toBeInTheDocument();

    server.use(http.get(`${API_URL}/api/v1/me/`, () => HttpResponse.json(fakeMe())));
    await userEvent.click(screen.getByRole("button", { name: fr.common.retry }));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
  });

  it("s'affiche si le service OIDC est injoignable à la connexion", async () => {
    const oidc = mockOidc(null);
    oidc.signinRedirect = vi.fn().mockRejectedValue(new Error("discovery failed"));
    renderApp("/connexion", oidc);
    await userEvent.click(await screen.findByRole("button", { name: fr.auth.login }));
    expect(await screen.findByText(fr.errors.unreachable)).toBeInTheDocument();
  });
});
