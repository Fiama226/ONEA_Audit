import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { authValueFor } from "@/test/shell";
import { actionSuivieFixture } from "./fixtures";
import type { ActionSuivie } from "./types";

export * from "./fixtures";

/** Action suivie par défaut (à lancer, dans les délais) ; `overrides` adapte le scénario. */
export function aSuiviAction(overrides: Partial<ActionSuivie> = {}): ActionSuivie {
  return { ...actionSuivieFixture, ...overrides } as ActionSuivie;
}

/** Client de requêtes de test : pas de nouvelle tentative. */
export function aTestClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/** Rend `ui` avec client, authentification et routeur (à l'adresse `path`) pour un rôle donné. */
export function renderSuivi(ui: ReactElement, role: Role = "AUDITE", path = "/") {
  const client = aTestClient();
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role, vi.fn())}>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, client };
}
