import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, configure, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { ROLES } from "@/auth/types";
import { AuthContext } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { appRoutes } from "@/routes";
import { rolesFor } from "@/layouts/navigation";
import { API_URL, server } from "@/test/msw";
import { authValueFor, meFor } from "@/test/shell";
import type { TutorielEtat } from "./api";
import { etapesPour, TUTORIEL_VERSION } from "./etapes";

beforeAll(() => {
  vi.setConfig({ testTimeout: 30000 });
  configure({ asyncUtilTimeout: 15000 });
});
afterEach(() => sessionStorage.clear());

const T = fr.tutoriel;
const URL_TUTO = `${API_URL}/api/v1/me/tutoriel/`;
const VU: TutorielEtat = { version_vue: TUTORIEL_VERSION, termine_le: "2026-11-01T10:00:00Z" };
const JAMAIS: TutorielEtat = { version_vue: null, termine_le: null };

/** Enregistre les POST reçus ; `echec` simule une panne réseau. */
function mockTutoriel(echec = false) {
  const actions: { action: string; version: number }[] = [];
  server.use(
    http.post(URL_TUTO, async ({ request }) => {
      if (echec) return HttpResponse.error();
      const body = (await request.json()) as { action: string; version: number };
      actions.push(body);
      return HttpResponse.json(body.action === "reinitialiser" ? JAMAIS : VU);
    }),
  );
  return actions;
}

function renderAt(path: string, role: Role, tutoriel: TutorielEtat) {
  const base = authValueFor(role);
  const value = { ...base, me: meFor(role, { tutoriel }) };
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={value}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, router };
}

const bienvenue = () => screen.queryByRole("dialog", { name: T.welcomeTitle });
const visite = () => screen.queryByTestId("tutoriel-visite");

describe("Tutoriel : affichage", () => {
  it("propose la visite au premier passage", async () => {
    renderAt("/", "RAI", JAMAIS);
    expect(await screen.findByRole("dialog", { name: T.welcomeTitle })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.start })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: T.later })).toBeInTheDocument();
  });

  it("ne masque pas « Mon compte » au premier passage, puis la propose ailleurs", async () => {
    const { router } = renderAt("/mon-compte", "RAI", JAMAIS);
    await screen.findByRole("heading", { name: T.accountTitle });
    expect(bienvenue()).not.toBeInTheDocument();
    await act(() => router.navigate("/"));
    expect(await screen.findByRole("dialog", { name: T.welcomeTitle })).toBeInTheDocument();
  });

  it("la reproposer si la version vue est antérieure", async () => {
    renderAt("/", "RAI", { version_vue: TUTORIEL_VERSION - 1, termine_le: null });
    expect(await screen.findByRole("dialog", { name: T.welcomeTitle })).toBeInTheDocument();
  });

  it("ne l'affiche pas si la version courante a été vue", async () => {
    renderAt("/", "RAI", VU);
    await screen.findByRole("main");
    expect(bienvenue()).not.toBeInTheDocument();
  });

  it("ne l'affiche pas si la session l'a déjà traitée", async () => {
    sessionStorage.setItem(`onea.tutoriel.v${TUTORIEL_VERSION}.1`, "1");
    renderAt("/", "RAI", JAMAIS);
    await screen.findByRole("main");
    expect(bienvenue()).not.toBeInTheDocument();
  });

  it("« Plus tard » enregistre « ignorer » et ferme", async () => {
    const actions = mockTutoriel();
    renderAt("/", "RAI", JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.later }));
    await waitFor(() =>
      expect(actions).toEqual([{ action: "ignorer", version: TUTORIEL_VERSION }]),
    );
    expect(bienvenue()).not.toBeInTheDocument();
  });

  it("ne bloque pas et ne rebondit pas si l'enregistrement échoue", async () => {
    mockTutoriel(true);
    const { unmount } = renderAt("/", "RAI", JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.later }));
    expect(bienvenue()).not.toBeInTheDocument();
    unmount();
    renderAt("/", "RAI", JAMAIS);
    await screen.findByRole("main");
    expect(bienvenue()).not.toBeInTheDocument();
  });
});

describe("Tutoriel : étapes par rôle", () => {
  it.each(ROLES)("%s : seulement des routes accessibles et des cibles présentes", async (role) => {
    const etapes = etapesPour(role);
    for (const e of etapes) {
      if (e.route) expect(rolesFor(e.route)?.includes(role) ?? true).toBe(true);
    }
    mockTutoriel();
    renderAt("/", role, JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.start }));
    const titres: string[] = [];
    for (let i = 0; i < etapes.length; i++) {
      const dialog = await screen.findByRole("dialog");
      titres.push(dialog.querySelector("h2")?.textContent ?? "");
      expect(dialog).toHaveTextContent(`${i + 1} / ${etapes.length}`);
      await userEvent.click(
        screen.getByRole("button", { name: i === etapes.length - 1 ? T.finish : T.next }),
      );
    }
    expect(titres).toEqual(etapes.map((e) => T.steps[e.id].title));
    expect(visite()).not.toBeInTheDocument();
  });

  it("différencie les rôles", () => {
    const ids = (r: Role) => etapesPour(r).map((e) => e.id);
    expect(ids("ADMIN")).toContain("administration");
    expect(ids("ADMIN")).not.toContain("missions");
    expect(ids("DG")).toContain("rapports");
    expect(ids("DG")).not.toContain("missions");
    expect(ids("AUDITE")).toContain("documents");
    expect(ids("AUDITEUR")).not.toContain("administration");
  });
});

describe("Tutoriel : clavier et fermeture", () => {
  it("navigue aux flèches et Échap ignore", async () => {
    const actions = mockTutoriel();
    renderAt("/", "RAI", JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.start }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("1 /");
    await userEvent.keyboard("{ArrowRight}");
    expect(await screen.findByRole("dialog")).toHaveTextContent("2 /");
    await userEvent.keyboard("{ArrowLeft}");
    expect(await screen.findByRole("dialog")).toHaveTextContent("1 /");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(visite()).not.toBeInTheDocument());
    await waitFor(() =>
      expect(actions).toEqual([{ action: "ignorer", version: TUTORIEL_VERSION }]),
    );
  });

  it("Échap sur la bienvenue équivaut à « Plus tard »", async () => {
    const actions = mockTutoriel();
    renderAt("/", "RAI", JAMAIS);
    await screen.findByRole("dialog", { name: T.welcomeTitle });
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(bienvenue()).not.toBeInTheDocument());
    await waitFor(() => expect(actions[0]?.action).toBe("ignorer"));
  });

  it("piège le focus dans la bulle", async () => {
    mockTutoriel();
    renderAt("/", "RAI", JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.start }));
    const dialog = await screen.findByRole("dialog");
    for (let i = 0; i < 8; i++) {
      await userEvent.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
    await userEvent.tab({ shift: true });
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
  });

  it("« Terminer » à la dernière étape enregistre « terminer »", async () => {
    const actions = mockTutoriel();
    renderAt("/", "ADMIN", JAMAIS);
    await userEvent.click(await screen.findByRole("button", { name: T.start }));
    const n = etapesPour("ADMIN").length;
    for (let i = 0; i < n - 1; i++)
      await userEvent.click(await screen.findByRole("button", { name: T.next }));
    await userEvent.click(await screen.findByRole("button", { name: T.finish }));
    await waitFor(() =>
      expect(actions).toEqual([{ action: "terminer", version: TUTORIEL_VERSION }]),
    );
  });
});

describe("Tutoriel : revoir la visite", () => {
  it("le bouton de « Mon compte » réinitialise et relance", async () => {
    const actions = mockTutoriel();
    renderAt("/mon-compte", "AUDITEUR", VU);
    expect(
      await screen.findByRole("heading", { level: 1, name: T.accountTitle }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: T.replay }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("1 /");
    await waitFor(() =>
      expect(actions).toEqual([{ action: "reinitialiser", version: TUTORIEL_VERSION }]),
    );
  });

  it("le menu utilisateur propose le compte et la visite", async () => {
    mockTutoriel();
    renderAt("/", "RAI", VU);
    await userEvent.click(
      await screen.findByRole("button", {
        name: new RegExp(T.menuAccount.slice(0, 0) + fr.shell.userMenu),
      }),
    );
    expect(await screen.findByRole("menuitem", { name: T.menuAccount })).toHaveAttribute(
      "href",
      "/mon-compte",
    );
    await userEvent.click(screen.getByRole("menuitem", { name: T.menuTour }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("1 /");
  });

  it("n'apparaît pas sur la page de connexion", async () => {
    const value = { ...authValueFor("RAI"), status: "anonymous" as const, me: undefined };
    const router = createMemoryRouter(appRoutes, { initialEntries: ["/connexion"] });
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={value}>
          <RouterProvider router={router} />
        </AuthContext.Provider>
      </QueryClientProvider>,
    );
    await screen.findByRole("button", { name: fr.auth.login });
    expect(bienvenue()).not.toBeInTheDocument();
  });
});

describe("Tutoriel : accessibilité", () => {
  it("bienvenue, étape et page « Mon compte » sans violation axe", async () => {
    mockTutoriel();
    const { baseElement } = renderAt("/", "RAI", JAMAIS);
    await screen.findByRole("dialog", { name: T.welcomeTitle });
    const opts = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe(baseElement, opts)).violations).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: T.start }));
    await screen.findByTestId("tutoriel-visite");
    expect((await axe(baseElement, opts)).violations).toEqual([]);
  });

  it("la page « Mon compte » est accessible", async () => {
    const { baseElement } = renderAt("/mon-compte", "DG", VU);
    await screen.findByRole("heading", { level: 1, name: T.accountTitle });
    const r = await axe(baseElement, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations).toEqual([]);
  });
});
