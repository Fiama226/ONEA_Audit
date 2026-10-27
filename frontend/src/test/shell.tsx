import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/auth/useAuth";
import type { Me, Role } from "@/auth/types";

export function meFor(role: Role, overrides: Partial<Me> = {}): Me {
  return {
    id: 1,
    username: role.toLowerCase(),
    email: `${role.toLowerCase()}@onea.bf`,
    first_name: "Awa",
    last_name: "Ouedraogo",
    role,
    direction_code: "DAI",
    fonction: "Fonction",
    ...overrides,
  };
}

export function authValueFor(
  role: Role,
  logout: AuthContextValue["logout"] = vi.fn().mockResolvedValue(undefined),
): AuthContextValue {
  return {
    status: "authenticated",
    me: meFor(role),
    sessionExpired: false,
    login: vi.fn().mockResolvedValue(undefined),
    logout,
    retry: vi.fn().mockResolvedValue(undefined),
    completeLogin: vi.fn().mockResolvedValue("/"),
  };
}

/** Rend `routes` dans un routeur mémoire avec un utilisateur authentifié du rôle donné. */
export function renderRoutes(
  routes: RouteObject[],
  role: Role,
  opts: { path?: string; logout?: AuthContextValue["logout"] } = {},
) {
  const value = authValueFor(role, opts.logout);
  const router = createMemoryRouter(routes, { initialEntries: [opts.path ?? "/"] });
  const utils = render(
    <AuthContext.Provider value={value}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  );
  return { ...utils, router, auth: value };
}

export function renderWithAuth(ui: ReactElement, role: Role, path = "/") {
  return renderRoutes([{ path: "*", element: ui }], role, { path });
}
