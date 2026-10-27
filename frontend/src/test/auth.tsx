import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import { AuthProvider } from "@/auth/AuthProvider";
import type { OidcClient, OidcUser } from "@/auth/oidc";
import type { Me } from "@/auth/types";
import { appRoutes } from "@/routes";
import { API_URL, server } from "./msw";

export function fakeUser(overrides: Partial<OidcUser> = {}): OidcUser {
  return { access_token: "tok-123", expired: false, state: undefined, ...overrides };
}

export function fakeMe(overrides: Partial<Record<keyof Me, unknown>> = {}) {
  return {
    id: 1,
    username: "rai",
    email: "rai@onea.bf",
    first_name: "Awa",
    last_name: "Ouedraogo",
    role: "RAI",
    direction_code: "DAI",
    fonction: "Responsable audit interne",
    ...overrides,
  };
}

export function mockOidc(user: OidcUser | null = null): OidcClient {
  return {
    getUser: vi.fn().mockResolvedValue(user),
    signinRedirect: vi.fn().mockResolvedValue(undefined),
    signinRedirectCallback: vi.fn().mockResolvedValue(user ?? fakeUser()),
    signoutRedirect: vi.fn().mockResolvedValue(undefined),
    removeUser: vi.fn().mockResolvedValue(undefined),
    events: { addUserLoaded: vi.fn(), removeUserLoaded: vi.fn() },
  };
}

export function serveMe(body: object = fakeMe()) {
  server.use(http.get(`${API_URL}/api/v1/me/`, () => HttpResponse.json(body)));
}

export function renderApp(path: string, oidc: OidcClient) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(
    <AuthProvider userManager={oidc}>
      <RouterProvider router={router} />
    </AuthProvider>,
  );
  return router;
}
