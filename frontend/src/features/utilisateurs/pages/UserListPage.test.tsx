import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { aListAccount, renderAdministration } from "../testUtils";

const findRow = () => screen.findByRole("link", { name: "Landry Kabore" }, { timeout: 10000 });
const LIST = `${API_URL}/api/v1/user-accounts/`;

function mockList(results = [aListAccount()], urls: URL[] = []) {
  server.use(
    http.get(LIST, ({ request }) => {
      urls.push(new URL(request.url));
      return HttpResponse.json({ count: results.length, next: null, previous: null, results });
    }),
    http.get(`${API_URL}/api/v1/directions/`, () =>
      HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [{ id: 1, code: "DAI", libelle: "Département Audit Interne" }],
      }),
    ),
  );
  return urls;
}

describe("UserListPage", () => {
  it("requests page 1 ordered by last name first", async () => {
    const urls = mockList();
    renderAdministration("/administration/utilisateurs");
    await findRow();
    expect(urls[0]?.search).toBe("?page=1&ordering=last_name");
  });

  it("shows the title, the directory note and one row in full", async () => {
    mockList([
      aListAccount({
        role: "AUDITE",
        direction_code: "DEX",
        is_active: false,
        en_attente_connexion: false,
      }),
    ]);
    renderAdministration("/administration/utilisateurs");
    const link = await findRow();
    expect(link).toHaveAttribute("href", "/administration/utilisateurs/7");
    expect(screen.getByRole("heading", { name: "Utilisateurs", level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/Les comptes sont créés et administrés/)).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Audité")).toBeInTheDocument();
    expect(screen.getByText("DEX (inconnue du référentiel)")).toBeInTheDocument();
    expect(screen.getByText("Désactivé")).toBeInTheDocument();
    expect(screen.getByText("28/10/2026")).toBeInTheDocument();
  });

  it("shows no provisional role nor any Keycloak notion", async () => {
    mockList([
      aListAccount({ en_attente_connexion: true, origine: "CSV", keycloak_sync_statut: "ECHEC" }),
    ]);
    renderAdministration("/administration/utilisateurs");
    await findRow();
    expect(document.body).not.toHaveTextContent(/provisoire|keycloak|annuaire|synchronisation/i);
  });

  it("offers Nouvel agent to a delegate allowed to create, without the CSV import", async () => {
    mockList();
    renderAdministration("/administration/utilisateurs", "AUDITEUR", {
      gestion_comptes: { creer: true, reinitialiser: false, roles: false, desactiver: false },
    });
    await findRow();
    expect(screen.getByRole("button", { name: "Nouvel agent" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Importer un fichier CSV" })).toBeNull();
  });

  it("filters on deactivated accounts and goes back to page 1", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    renderAdministration("/administration/utilisateurs?page=3");
    await findRow();
    await user.selectOptions(screen.getByLabelText("Statut"), "Désactivés");
    await waitFor(() => expect(urls.at(-1)?.searchParams.get("is_active")).toBe("false"));
    expect(urls.at(-1)?.searchParams.get("page")).toBe("1");
  });

  it("filters on accounts pending first login", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    renderAdministration("/administration/utilisateurs");
    await findRow();
    await user.selectOptions(screen.getByLabelText("Statut"), "En attente de première connexion");
    await waitFor(() => expect(urls.at(-1)?.searchParams.get("en_attente_connexion")).toBe("true"));
  });

  it("sends the search term once after the debounce", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    renderAdministration("/administration/utilisateurs");
    await findRow();
    await user.type(screen.getByLabelText("Rechercher (nom, identifiant, matricule)"), "ouedr");
    await waitFor(() => expect(urls.some((u) => u.searchParams.get("q") === "ouedr")).toBe(true));
    expect(urls.filter((u) => u.searchParams.has("q"))).toHaveLength(1);
  });

  it("restores filters and page from the URL", async () => {
    const urls = mockList();
    renderAdministration("/administration/utilisateurs?statut=inactif&page=2");
    expect(await screen.findByLabelText("Statut")).toHaveValue("inactif");
    await waitFor(() => expect(urls.length).toBeGreaterThan(0));
    expect(urls[0]?.searchParams.get("is_active")).toBe("false");
    expect(urls[0]?.searchParams.get("page")).toBe("2");
  });

  it("explains an empty directory without filters", async () => {
    mockList([]);
    renderAdministration("/administration/utilisateurs");
    expect(await screen.findByText("Aucun compte pour le moment.")).toBeInTheDocument();
    expect(
      screen.getByText("Créez un compte avec « Nouvel agent » ou importez un fichier CSV."),
    ).toBeInTheDocument();
  });

  it("only mentions the actions a delegate can see in the empty state", async () => {
    mockList([]);
    const { unmount } = renderAdministration("/administration/utilisateurs", "AUDITEUR", {
      gestion_comptes: { creer: true, reinitialiser: false, roles: false, desactiver: false },
    });
    expect(await screen.findByText("Créez un compte avec « Nouvel agent ».")).toBeInTheDocument();
    unmount();
    renderAdministration("/administration/utilisateurs", "AUDITEUR", {
      gestion_comptes: { creer: false, reinitialiser: true, roles: false, desactiver: false },
    });
    expect(
      await screen.findByText("Les comptes créés dans la plateforme apparaîtront ici."),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/Nouvel agent|CSV/);
  });

  it("offers to clear filters when nothing matches", async () => {
    mockList([]);
    const user = userEvent.setup();
    renderAdministration("/administration/utilisateurs?role=DG");
    expect(
      await screen.findByText("Aucun utilisateur ne correspond aux filtres."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Effacer les filtres" }));
    expect(await screen.findByLabelText("Rôle")).toHaveValue("");
  });

  it("shows an error when the list cannot be loaded", async () => {
    server.use(http.get(LIST, () => HttpResponse.json({}, { status: 500 })));
    renderAdministration("/administration/utilisateurs");
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
  });

  it("limits the search input to 100 characters", async () => {
    mockList();
    renderAdministration("/administration/utilisateurs");
    await findRow();
    expect(screen.getByLabelText("Rechercher (nom, identifiant, matricule)")).toHaveAttribute(
      "maxlength",
      "100",
    );
  });

  it("does not push stale search text back after browser Back", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    const { router } = renderAdministration("/administration/utilisateurs");
    await findRow();
    const input = screen.getByLabelText("Rechercher (nom, identifiant, matricule)");
    await user.type(input, "ouedr");
    await waitFor(() => expect(router.state.location.search).toContain("q=ouedr"));
    await act(() => router.navigate(-1));
    await waitFor(() => expect(input).toHaveValue(""));
    await new Promise((r) => setTimeout(r, 500));
    expect(router.state.location.search).not.toContain("q=");
    expect(urls.at(-1)?.searchParams.has("q")).toBe(false);
  });

  it("ignores a whitespace-only search and invalid URL values", async () => {
    const urls = mockList();
    renderAdministration(
      "/administration/utilisateurs?q=%20%20&role=BOSS&sync=NOPE&statut=zzz&page=abc&ordering=password",
    );
    await findRow();
    expect(urls[0]?.search).toBe("?page=1&ordering=last_name");
  });

  it("writes the sort order to the URL and requests it", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    const { router } = renderAdministration("/administration/utilisateurs");
    await findRow();
    await user.click(screen.getByRole("button", { name: /Rôle/ }));
    await waitFor(() => expect(router.state.location.search).toBe("?ordering=role"));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get("ordering")).toBe("role"));
  });

  it("writes the page to the URL when paginating", async () => {
    const urls: URL[] = [];
    server.use(
      http.get(LIST, ({ request }) => {
        urls.push(new URL(request.url));
        return HttpResponse.json({
          count: 60,
          next: null,
          previous: null,
          results: [aListAccount()],
        });
      }),
    );
    const user = userEvent.setup();
    const { router } = renderAdministration("/administration/utilisateurs");
    await findRow();
    await user.click(screen.getByRole("button", { name: "Page suivante" }));
    await waitFor(() => expect(router.state.location.search).toBe("?page=2"));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get("page")).toBe("2"));
  });

  it("goes back to page 1 when the search changes", async () => {
    const urls = mockList();
    const user = userEvent.setup();
    renderAdministration("/administration/utilisateurs?page=3");
    await findRow();
    await user.type(screen.getByLabelText("Rechercher (nom, identifiant, matricule)"), "kab");
    await waitFor(() => expect(urls.at(-1)?.searchParams.get("q")).toBe("kab"));
    expect(urls.at(-1)?.searchParams.get("page")).toBe("1");
  });

  it("announces the result count politely", async () => {
    mockList();
    renderAdministration("/administration/utilisateurs");
    await findRow();
    const status = screen
      .getAllByRole("status")
      .find((el) => el.getAttribute("aria-live") === "polite" && /1 résultat/.test(el.textContent));
    expect(status).toBeDefined();
  });

  it("has no accessibility violation", async () => {
    mockList();
    const { container } = renderAdministration("/administration/utilisateurs");
    await findRow();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
