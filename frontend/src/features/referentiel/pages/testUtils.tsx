import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import type { Role } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { authValueFor } from "@/test/shell";
import { referentielRoutes } from "../routes";

/** Rend les routes du Référentiel (sous /referentiel) avec TanStack Query et un rôle donné. */
export function renderReferentiel(path: string, role: Role) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter([{ path: "/referentiel", children: referentielRoutes }], {
    initialEntries: [path],
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor(role, vi.fn())}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router };
}

export const page = <T,>(results: T[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
