import { configure, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { anAccount, renderAdministration } from "../testUtils";
import type { CompteUtilisateur } from "../types";

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 4000 });
});

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const ACCOUNT_URL = `${API_URL}/api/v1/user-accounts/7/`;
const paged = (results: object[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
const DAI = {
  id: "d1",
  code: "DAI",
  libelle: "Département Audit Interne",
  type: "DIRECTION",
  parent: null,
};

/** Sert la fiche (état mutable mis à jour par les actions), l'historique et les directions. */
function serve(initial: CompteUtilisateur) {
  const state = {
    account: initial,
    requests: [] as { method: string; url: string; body: unknown }[],
  };
  const record = async (request: Request) => {
    const text = await request.text();
    state.requests.push({
      method: request.method,
      url: new URL(request.url).pathname,
      body: text ? JSON.parse(text) : undefined,
    });
  };
  server.use(
    http.get(ACCOUNT_URL, () => HttpResponse.json(state.account)),
    http.get(`${API_URL}/api/v1/audit-log/`, () => HttpResponse.json(paged([]))),
    http.get(`${API_URL}/api/v1/directions/`, () => HttpResponse.json(paged([DAI]))),
  );
  return { state, record };
}

function open(path = "/administration/utilisateurs/7") {
  return renderAdministration(path);
}

describe("UserDetailPage", () => {
  it("shows identity, read-only role and a provisional role notice", async () => {
    serve(anAccount({ premiere_connexion_le: null }));
    open();
    expect(await screen.findByRole("heading", { name: "Landry Kabore" })).toBeInTheDocument();
    expect(screen.getByText("Lié à l'annuaire")).toBeInTheDocument();
    expect(screen.getByText("Import CSV")).toBeInTheDocument();
    expect(screen.getByText("Jamais connecté")).toBeInTheDocument();
    expect(screen.getByText(/Rôle provisoire saisi à l'import/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Rôle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Rôle" })).not.toBeInTheDocument();
  });

  it("shows the first login date and not-linked state", async () => {
    serve(
      anAccount({
        keycloak_lie: false,
        role_provisoire: false,
        premiere_connexion_le: "2026-10-28T08:00:00Z",
      }),
    );
    open();
    expect(await screen.findByText("Pas encore lié à l'annuaire")).toBeInTheDocument();
    expect(screen.getByText("Première connexion : 28/10/2026 08:00")).toBeInTheDocument();
    expect(screen.queryByText(/Rôle provisoire saisi/)).not.toBeInTheDocument();
    expect(screen.getByText(/rien à synchroniser dans Keycloak/)).toBeInTheDocument();
  });

  it("shows a not found message with a link back to the list", async () => {
    server.use(
      http.get(ACCOUNT_URL, () => HttpResponse.json({ detail: "Introuvable." }, { status: 404 })),
    );
    open();
    expect(await screen.findByText("Utilisateur introuvable.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Retour à la liste/ })).toHaveAttribute(
      "href",
      "/administration/utilisateurs",
    );
  });

  it("sends only the changed profile field", async () => {
    const { state, record } = serve(anAccount());
    server.use(
      http.patch(ACCOUNT_URL, async ({ request }) => {
        await record(request);
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    const save = await screen.findByRole("button", { name: "Enregistrer le profil" });
    expect(save).toBeDisabled();
    const fonction = screen.getByRole("textbox", { name: "Fonction" });
    await user.clear(fonction);
    await user.type(fonction, "Chef de service");
    await user.click(save);
    await screen.findByText("Profil enregistré.");
    expect(state.requests).toEqual([
      { method: "PATCH", url: "/api/v1/user-accounts/7/", body: { fonction: "Chef de service" } },
    ]);
  });

  it("keeps a direction missing from the options selected and does not send it", async () => {
    const { state, record } = serve(anAccount({ direction_code: "DEX", direction_libelle: null }));
    server.use(
      http.patch(ACCOUNT_URL, async ({ request }) => {
        await record(request);
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    const select = await screen.findByRole("combobox", { name: "Direction" });
    await screen.findByRole("option", { name: "DAI — Département Audit Interne" });
    expect(select).toHaveValue("DEX");
    const matricule = screen.getByRole("textbox", { name: "Matricule" });
    await user.clear(matricule);
    await user.type(matricule, "M-001");
    await user.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
    await screen.findByText("Profil enregistré.");
    expect(state.requests[0]?.body).toEqual({ matricule: "M-001" });
  });

  it("shows server validation errors under the field", async () => {
    serve(anAccount());
    server.use(
      http.patch(ACCOUNT_URL, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { matricule: ["Matricule déjà utilisé."] } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();
    const matricule = await screen.findByRole("textbox", { name: "Matricule" });
    await user.type(matricule, "9");
    await user.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
    expect(await screen.findByText("Matricule déjà utilisé.")).toBeInTheDocument();
    expect(matricule).toHaveAccessibleDescription("Matricule déjà utilisé.");
  });

  it("offers to restore directory sync only for a locally managed profile", async () => {
    serve(anAccount({ profil_gere_localement: false }));
    open();
    expect(await screen.findByText(/proviennent de l'annuaire/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rétablir la synchronisation" })).toBeNull();
  });

  it("restores directory sync with a POST", async () => {
    const { state, record } = serve(anAccount());
    server.use(
      http.post(`${ACCOUNT_URL}resync-profile/`, async ({ request }) => {
        await record(request);
        state.account = anAccount({ profil_gere_localement: false });
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    expect(await screen.findByText(/ne sont plus mises à jour depuis l'annuaire/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Rétablir la synchronisation" }));
    expect(await screen.findByText(/proviennent de l'annuaire/)).toBeInTheDocument();
    expect(state.requests[0]?.url).toBe("/api/v1/user-accounts/7/resync-profile/");
  });

  it("hides the deactivate button when the action is not allowed", async () => {
    serve(anAccount({ is_active: true, actions: { ...anAccount().actions, desactiver: false } }));
    open();
    await screen.findByRole("heading", { name: "Landry Kabore" });
    expect(screen.queryByRole("button", { name: "Désactiver le compte" })).not.toBeInTheDocument();
  });

  const ACTIVE = () =>
    anAccount({
      is_active: true,
      desactive_le: null,
      desactive_par: null,
      motif_desactivation: "",
      keycloak_sync: { ...anAccount().keycloak_sync, statut: "A_JOUR", erreur: "", manuel: false },
      keycloak_sync_statut: "A_JOUR",
      actions: { ...anAccount().actions, desactiver: true, reactiver: false },
    });
  const DEACTIVATED = (statut: "A_JOUR" | "ECHEC" | "EN_ATTENTE", extra = {}) =>
    anAccount({
      is_active: false,
      keycloak_sync: {
        ...anAccount().keycloak_sync,
        statut,
        erreur: statut === "ECHEC" ? "Keycloak a refusé l'opération (HTTP 403)." : "",
        manuel: statut === "ECHEC",
      },
      keycloak_sync_statut: statut,
      desactive_le: "2026-10-28T08:00:00Z",
      desactive_par: { id: 1, username: "admin", nom_complet: "Admin Plateforme" },
      motif_desactivation: "Départ",
      ...extra,
    });

  it("requires a reason before deactivating", async () => {
    const { state, record } = serve(ACTIVE());
    server.use(
      http.post(`${ACCOUNT_URL}deactivate/`, async ({ request }) => {
        await record(request);
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Désactiver le compte" }));
    const dialog = await screen.findByRole("alertdialog", {
      name: "Désactiver le compte de Landry Kabore ?",
    });
    expect(dialog).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Motif" }), "   ");
    await user.click(screen.getByRole("button", { name: "Désactiver" }));
    expect(await screen.findByText("Le motif est obligatoire.")).toBeInTheDocument();
    expect(state.requests).toHaveLength(0);
  });

  it("keeps the dialog open and shows the refusal when deactivation is refused", async () => {
    serve(ACTIVE());
    server.use(
      http.post(`${ACCOUNT_URL}deactivate/`, () =>
        HttpResponse.json(
          {
            detail: "Le dernier administrateur ne peut pas être désactivé.",
            code: "DERNIER_ADMIN",
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Désactiver le compte" }));
    await user.type(await screen.findByRole("textbox", { name: "Motif" }), "Départ");
    await user.click(screen.getByRole("button", { name: "Désactiver" }));
    expect(await screen.findByText(/dernier administrateur/)).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("deactivates with a reason and shows the result", async () => {
    const { state, record } = serve(ACTIVE());
    server.use(
      http.post(`${ACCOUNT_URL}deactivate/`, async ({ request }) => {
        await record(request);
        state.account = DEACTIVATED("A_JOUR");
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Désactiver le compte" }));
    await user.type(await screen.findByRole("textbox", { name: "Motif" }), "  Départ ");
    await user.click(screen.getByRole("button", { name: "Désactiver" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(state.requests[0]?.body).toEqual({ motif: "Départ" });
    expect(await screen.findByText("Compte désactivé dans la plateforme.")).toBeInTheDocument();
    expect(
      screen.getByText("Désactivé le 28/10/2026 08:00 par Admin Plateforme — Motif : Départ"),
    ).toBeInTheDocument();
    expect(screen.getByText("Keycloak : compte désactivé, sessions fermées")).toBeInTheDocument();
  });

  it("shows the Keycloak failure after deactivation and retries manually", async () => {
    const { state, record } = serve(ACTIVE());
    server.use(
      http.post(`${ACCOUNT_URL}deactivate/`, () => {
        state.account = DEACTIVATED("ECHEC");
        return HttpResponse.json(state.account);
      }),
      http.post(`${ACCOUNT_URL}retry-keycloak-sync/`, async ({ request }) => {
        await record(request);
        state.account = DEACTIVATED("A_JOUR");
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Désactiver le compte" }));
    await user.type(await screen.findByRole("textbox", { name: "Motif" }), "Départ");
    await user.click(screen.getByRole("button", { name: "Désactiver" }));
    const alert = await screen.findByText(/La synchronisation avec Keycloak a échoué/);
    expect(alert).toHaveTextContent("Keycloak a refusé l'opération (HTTP 403).");
    expect(alert).toHaveTextContent("L'accès à la plateforme est néanmoins coupé.");
    expect(screen.getByText(/relancez la synchronisation manuellement/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Relancer la synchronisation" }));
    expect(
      await screen.findByText("Keycloak : compte désactivé, sessions fermées"),
    ).toBeInTheDocument();
    expect(state.requests[0]?.url).toBe("/api/v1/user-accounts/7/retry-keycloak-sync/");
  });

  it("shows a pending sync without a retry button when not allowed", async () => {
    serve(
      DEACTIVATED("EN_ATTENTE", {
        actions: { ...anAccount().actions, relancer_synchro_keycloak: false },
      }),
    );
    open();
    expect(await screen.findByText(/Synchronisation avec Keycloak en attente/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Relancer la synchronisation" })).toBeNull();
  });

  it("reactivates an account", async () => {
    const { state, record } = serve(DEACTIVATED("A_JOUR"));
    server.use(
      http.post(`${ACCOUNT_URL}reactivate/`, async ({ request }) => {
        await record(request);
        state.account = ACTIVE();
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Réactiver le compte" }));
    await screen.findByRole("alertdialog", { name: "Réactiver le compte de Landry Kabore ?" });
    await user.click(screen.getByRole("button", { name: "Réactiver" }));
    expect(await screen.findByText("Compte réactivé dans la plateforme.")).toBeInTheDocument();
    expect(screen.getByText("Compte actif")).toBeInTheDocument();
    expect(state.requests).toHaveLength(1);
  });

  it("marks every action button as hidden when printing", async () => {
    serve(anAccount());
    open();
    await screen.findByRole("heading", { name: "Landry Kabore" });
    for (const name of [
      "Enregistrer le profil",
      "Rétablir la synchronisation",
      "Relancer la synchronisation",
      "Réactiver le compte",
    ]) {
      expect(screen.getByRole("button", { name }).closest(".print\\:hidden")).not.toBeNull();
    }
  });

  it("has no accessibility violation, dialog and alert included", async () => {
    serve(DEACTIVATED("ECHEC", { actions: { ...anAccount().actions, desactiver: true } }));
    const user = userEvent.setup();
    const { container } = open();
    await screen.findByRole("alert");
    const page = await axe(container, NO_CONTRAST);
    expect(page.violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Désactiver le compte" }));
    const dialog = await screen.findByRole("alertdialog");
    const modal = await axe(dialog, NO_CONTRAST);
    expect(modal.violations).toEqual([]);
  });
});
