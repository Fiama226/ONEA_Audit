import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, configure, render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { beforeAll, vi } from "vitest";
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
    tutoriel: { version_vue: 1, termine_le: null },
    otp_connexion_actif: false,
    // An active ADMIN holds every account-management right; other roles none by default.
    gestion_comptes: {
      creer: role === "ADMIN",
      reinitialiser: role === "ADMIN",
      roles: role === "ADMIN",
      desactiver: role === "ADMIN",
    },
    ...overrides,
  };
}

export function authValueFor(
  role: Role,
  logout: AuthContextValue["logout"] = vi.fn().mockResolvedValue(undefined),
  me: Partial<Me> = {},
): AuthContextValue {
  return {
    status: "authenticated",
    me: meFor(role, me),
    etape: "OK",
    sessionExpired: false,
    loggedOut: false,
    login: vi.fn().mockResolvedValue("OK"),
    verifyOtp: vi.fn().mockResolvedValue("OK"),
    changePassword: vi.fn().mockResolvedValue(undefined),
    logout,
    retry: vi.fn().mockResolvedValue(undefined),
    updateMe: vi.fn(),
  };
}

/**
 * Rend `routes` dans un routeur mémoire avec un utilisateur authentifié du rôle donné ;
 * `me` complète son profil (ex. droits délégués `gestion_comptes`).
 */
export function renderRoutes(
  routes: RouteObject[],
  role: Role,
  opts: { path?: string; logout?: AuthContextValue["logout"]; me?: Partial<Me> } = {},
) {
  const value = authValueFor(role, opts.logout, opts.me);
  const router = createMemoryRouter(routes, { initialEntries: [opts.path ?? "/"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={value}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router, auth: value, client };
}

export function renderWithAuth(ui: ReactElement, role: Role, path = "/", me: Partial<Me> = {}) {
  return renderRoutes([{ path: "*", element: ui }], role, { path, me });
}

/** Simule `window.matchMedia` ; `set` bascule une requête et notifie ses écouteurs. */
export function mockMatchMedia(initial: Record<string, boolean> = {}) {
  type Listener = (e: MediaQueryListEvent) => void;
  const state = new Map(Object.entries(initial));
  const listeners = new Map<string, Set<Listener>>();
  vi.stubGlobal("matchMedia", (query: string): MediaQueryList => {
    const set = listeners.get(query) ?? new Set<Listener>();
    listeners.set(query, set);
    return {
      get matches() {
        return state.get(query) ?? false;
      },
      media: query,
      onchange: null,
      addEventListener: (_: string, cb: EventListenerOrEventListenerObject) => {
        set.add(cb as Listener);
      },
      removeEventListener: (_: string, cb: EventListenerOrEventListenerObject) => {
        set.delete(cb as Listener);
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    };
  });
  return {
    set(query: string, matches: boolean) {
      state.set(query, matches);
      act(() => {
        for (const cb of listeners.get(query) ?? []) {
          cb({ matches, media: query } as MediaQueryListEvent);
        }
      });
    },
  };
}

/**
 * À appeler en tête d'un fichier de tests qui monte le shell complet (lent sous jsdom) :
 * élargit les délais pour ce fichier seulement.
 */
export function allowSlowShell() {
  beforeAll(() => {
    vi.setConfig({ testTimeout: 20000 });
    configure({ asyncUtilTimeout: 15000 });
  });
}
