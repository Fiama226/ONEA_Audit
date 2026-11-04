import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Me, Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";
import {
  ALL_ACTIONS,
  aDelegation,
  anAccount,
  aTemporaryPassword,
  NO_ACTIONS,
  renderAdministration,
  rights,
} from "../testUtils";
import type { CompteUtilisateur, Delegation } from "../types";

allowSlowShell();

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const ACCOUNT_URL = `${API_URL}/api/v1/user-accounts/7/`;
const PASSWORD = "Tmp-9f3K-q7Lm-2xWz";
const DELEGATION_TITLE = "Délégation de la gestion des comptes";
const paged = (results: object[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

type Sent = { method: string; url: string; body: unknown };

/** Sert la fiche (mutable), sa délégation, l'historique et les directions ; trace les écritures. */
function serve(initial: CompteUtilisateur, delegation: Delegation = aDelegation()) {
  const state = { account: initial, delegation, sent: [] as Sent[], delegationReads: 0 };
  const record = async (request: Request) => {
    const text = await request.text();
    state.sent.push({
      method: request.method,
      url: new URL(request.url).pathname,
      body: text ? JSON.parse(text) : undefined,
    });
  };
  server.use(
    http.get(ACCOUNT_URL, () => HttpResponse.json(state.account)),
    http.get(`${ACCOUNT_URL}delegation/`, () => {
      state.delegationReads += 1;
      return HttpResponse.json(state.delegation);
    }),
    http.put(`${ACCOUNT_URL}delegation/`, async ({ request }) => {
      await record(request);
      const body = state.sent.at(-1)?.body as Omit<Delegation, "accorde_par" | "accorde_le">;
      state.delegation = {
        ...body,
        accorde_par: { id: 1, username: "admin", nom_complet: "Admin Plateforme" },
        accorde_le: "2026-11-04T10:00:00Z",
      };
      return HttpResponse.json(state.delegation);
    }),
    http.get(`${API_URL}/api/v1/audit-log/`, () => HttpResponse.json(paged([]))),
    http.get(`${API_URL}/api/v1/directions/`, () => HttpResponse.json(paged([]))),
  );
  return { state, record };
}

function open(role: Role = "ADMIN", me: Partial<Me> = {}) {
  return renderAdministration("/administration/utilisateurs/7", role, me);
}

const DELEGATE = (droits = {}) => ({ gestion_comptes: rights(droits) });

describe("UserDetailPage — délégation", () => {
  it("never shows nor reads the delegation for a non-ADMIN delegate", async () => {
    const { state } = serve(anAccount({ actions: { ...NO_ACTIONS, changer_role: true } }));
    open("RAI", DELEGATE({ roles: true, creer: true, reinitialiser: true, desactiver: true }));
    await screen.findByRole("heading", { name: "Landry Kabore" });
    expect(screen.queryByRole("heading", { name: DELEGATION_TITLE })).toBeNull();
    expect(screen.queryByRole("group", { name: "Droits délégués" })).toBeNull();
    expect(state.delegationReads).toBe(0);
  });

  it("does not offer a delegation on an administrator account", async () => {
    const { state } = serve(anAccount({ role: "ADMIN" }));
    open();
    await screen.findByRole("heading", { name: "Landry Kabore" });
    expect(screen.queryByRole("heading", { name: DELEGATION_TITLE })).toBeNull();
    expect(state.delegationReads).toBe(0);
  });

  it("lets an ADMIN set the four rights and warns about access to accounts", async () => {
    const { state } = serve(anAccount(), aDelegation({ creer: true }));
    const user = userEvent.setup();
    open();
    const group = await screen.findByRole("group", { name: "Droits délégués" });
    const box = (name: string) => within(group).getByRole("checkbox", { name });
    await waitFor(() => expect(box("Créer des comptes")).toBeChecked());
    expect(
      box("Réinitialiser les mots de passe et désactiver le code de connexion"),
    ).not.toBeChecked();
    expect(box("Changer les rôles et la direction")).not.toBeChecked();
    expect(box("Désactiver et réactiver des comptes")).not.toBeChecked();
    expect(
      screen.getByText(/peut ainsi obtenir l'accès à n'importe quel compte non administrateur/),
    ).toBeVisible();
    expect(
      screen.getByText(/Un délégué gère uniquement les comptes AUDITEUR et AUDITE/),
    ).toBeVisible();

    await user.click(box("Désactiver et réactiver des comptes"));
    await user.click(screen.getByRole("button", { name: "Enregistrer la délégation" }));
    expect(await screen.findByText("Délégation enregistrée.")).toBeVisible();
    expect(state.sent).toEqual([
      {
        method: "PUT",
        url: "/api/v1/user-accounts/7/delegation/",
        body: { creer: true, reinitialiser: false, roles: false, desactiver: true },
      },
    ]);
    expect(await screen.findByText(/Dernière modification le 04\/11\/2026/)).toBeVisible();
  });
});

describe("UserDetailPage — mot de passe et code de connexion", () => {
  it("resets the password and shows it once when it was not emailed", async () => {
    const { record } = serve(anAccount());
    server.use(
      http.post(`${ACCOUNT_URL}reset-password/`, async ({ request }) => {
        await record(request);
        return HttpResponse.json(aTemporaryPassword(), {
          headers: { "Cache-Control": "no-store" },
        });
      }),
    );
    const user = userEvent.setup();
    const { client } = open();
    const trigger = await screen.findByRole("button", { name: "Réinitialiser le mot de passe" });
    await user.click(trigger);
    const dialog = await screen.findByRole("alertdialog", {
      name: "Réinitialiser le mot de passe de Landry Kabore ?",
    });
    const send = within(dialog).getByRole("checkbox", {
      name: "Envoyer le nouveau mot de passe par courriel",
    });
    expect(send).toBeChecked();
    await user.click(send);
    await user.click(within(dialog).getByRole("button", { name: "Réinitialiser" }));
    expect(await within(dialog).findByText(PASSWORD)).toBeVisible();
    expect(within(dialog).getByText(/il ne sera plus jamais affiché/)).toBeVisible();
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);

    // Échap ne ferme pas la fenêtre tant que le mot de passe est affiché.
    await user.keyboard("{Escape}");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(within(dialog).getByText(PASSWORD)).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "J'ai noté le mot de passe, fermer" }),
    );
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(document.body).not.toHaveTextContent(PASSWORD);
    expect(
      JSON.stringify(
        client
          .getMutationCache()
          .getAll()
          .map((m) => m.state.data),
      ),
    ).not.toContain(PASSWORD);
    expect(trigger).toHaveFocus();
  });

  it("does not show any password when the new one was emailed", async () => {
    const { state, record } = serve(anAccount());
    server.use(
      http.post(`${ACCOUNT_URL}reset-password/`, async ({ request }) => {
        await record(request);
        return HttpResponse.json(
          aTemporaryPassword({ courriel_envoye: true, mot_de_passe_temporaire: null }),
        );
      }),
    );
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Réinitialiser le mot de passe" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Réinitialiser" }));
    expect(
      await within(dialog).findByText(
        /a été mis en file d'envoi par courriel pour l\.kabore@onea\.bf/,
      ),
    ).toBeVisible();
    expect(within(dialog).queryByText("Mot de passe temporaire")).toBeNull();
    expect(state.sent[0]?.body).toEqual({ envoyer_courriel: true });
  });

  it("hides the reset and code buttons without the right", async () => {
    serve(anAccount({ otp_connexion_actif: true, actions: NO_ACTIONS }));
    open("RAI", DELEGATE({ creer: true }));
    await screen.findByText("Code de connexion par courriel : activé.");
    expect(screen.queryByRole("button", { name: "Réinitialiser le mot de passe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Désactiver le code de connexion" })).toBeNull();
  });

  it("disables the login code of an agent after confirmation", async () => {
    const { state, record } = serve(
      anAccount({ otp_connexion_actif: true, actions: { ...ALL_ACTIONS, desactiver_otp: true } }),
    );
    server.use(
      http.post(`${ACCOUNT_URL}disable-otp/`, async ({ request }) => {
        await record(request);
        state.account = anAccount({ otp_connexion_actif: false });
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open("AUDITEUR", DELEGATE({ reinitialiser: true }));
    await user.click(
      await screen.findByRole("button", { name: "Désactiver le code de connexion" }),
    );
    const dialog = await screen.findByRole("alertdialog", {
      name: "Désactiver le code de connexion de Landry Kabore ?",
    });
    await user.click(within(dialog).getByRole("button", { name: "Désactiver le code" }));
    expect(await screen.findByText("Code de connexion désactivé.")).toBeVisible();
    expect(screen.getByText("Code de connexion par courriel : désactivé.")).toBeVisible();
    expect(state.sent.map((s) => s.url)).toEqual(["/api/v1/user-accounts/7/disable-otp/"]);
  });
});

describe("UserDetailPage — rôle et profil", () => {
  it("hides the role control from a delegate lacking the roles right", async () => {
    serve(anAccount({ actions: { ...NO_ACTIONS, modifier_profil: true } }));
    open("RAI", DELEGATE({ creer: true }));
    await screen.findByRole("heading", { name: "Landry Kabore" });
    expect(screen.getByText("Auditeur", { selector: "p" })).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "Nouveau rôle" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Changer le rôle" })).toBeNull();
  });

  it("changes the role; a delegate only picks AUDITEUR or AUDITE", async () => {
    const { state, record } = serve(anAccount());
    server.use(
      http.post(`${ACCOUNT_URL}change-role/`, async ({ request }) => {
        await record(request);
        state.account = anAccount({ role: "AUDITE" });
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open("AUDITEUR", DELEGATE({ roles: true }));
    const select = await screen.findByRole("combobox", { name: "Nouveau rôle" });
    const options = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    // Le rôle actuel (Auditeur) n'est pas reproposé ; ni Administrateur, ni RAI, ni DG.
    expect(options).toEqual(["Choisir un rôle", "Audité"]);
    expect(screen.getByRole("button", { name: "Changer le rôle" })).toBeDisabled();
    await user.selectOptions(select, "AUDITE");
    await user.click(screen.getByRole("button", { name: "Changer le rôle" }));
    // Confirmation explicite avant d'appliquer.
    const confirm = await screen.findByRole("alertdialog", {
      name: "Changer le rôle de Landry Kabore ?",
    });
    expect(confirm).toHaveTextContent(/passe de « Auditeur » à « Audité »/);
    expect(within(confirm).queryByText(/donne tous les droits/)).toBeNull();
    expect(state.sent).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "Confirmer le changement" }));
    expect(await screen.findByText("Rôle modifié.")).toBeVisible();
    expect(select).toHaveFocus();
    expect(state.sent).toEqual([
      { method: "POST", url: "/api/v1/user-accounts/7/change-role/", body: { role: "AUDITE" } },
    ]);
  });

  it("shows a role refusal from the server next to the control", async () => {
    serve(anAccount({ role: "ADMIN" }));
    server.use(
      http.post(`${ACCOUNT_URL}change-role/`, () =>
        HttpResponse.json(
          { detail: "Le dernier administrateur actif garde son rôle.", errors: {} },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    open();
    const select = await screen.findByRole("combobox", { name: "Nouveau rôle" });
    await user.selectOptions(select, "RAI");
    await user.click(screen.getByRole("button", { name: "Changer le rôle" }));
    await user.click(await screen.findByRole("button", { name: "Confirmer le changement" }));
    expect(
      await screen.findByText("Le dernier administrateur actif garde son rôle."),
    ).toBeVisible();
    expect(select).toHaveAccessibleDescription(/Le dernier administrateur actif garde son rôle\./);
  });

  it("warns explicitly before granting Administrateur, and cancelling sends nothing", async () => {
    const { state } = serve(anAccount());
    const user = userEvent.setup();
    open();
    const select = await screen.findByRole("combobox", { name: "Nouveau rôle" });
    await user.selectOptions(select, "ADMIN");
    await user.click(screen.getByRole("button", { name: "Changer le rôle" }));
    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText(/le rôle Administrateur donne tous les droits/)).toBeVisible();
    expect((await axe(confirm, NO_CONTRAST)).violations).toEqual([]);
    await user.click(within(confirm).getByRole("button", { name: "Annuler" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(state.sent).toHaveLength(0);
    expect(select).toHaveValue("ADMIN");
  });

  it("explains why every profile field is greyed for a delegate with no profile right", async () => {
    serve(anAccount({ actions: { ...NO_ACTIONS, desactiver: true } }));
    open("RAI", DELEGATE({ desactiver: true }));
    const first = await screen.findByRole("textbox", { name: "Prénom" });
    expect(first).toBeDisabled();
    expect(screen.getByText(/Les champs grisés demandent un droit/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Enregistrer le profil" })).toBeNull();
  });

  it("does not validate an unchanged or greyed email", async () => {
    const { state, record } = serve(
      anAccount({
        email: "ancienne-adresse@",
        actions: { ...NO_ACTIONS, modifier_profil: true, modifier_courriel: false },
      }),
    );
    server.use(
      http.patch(ACCOUNT_URL, async ({ request }) => {
        await record(request);
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open("RAI", DELEGATE({ creer: true }));
    const fonction = await screen.findByRole("textbox", { name: "Fonction" });
    await user.type(fonction, " principal");
    await user.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
    await screen.findByText("Profil enregistré.");
    expect(screen.queryByText("Saisissez une adresse de courriel valide.")).toBeNull();
    expect(state.sent[0]?.body).toEqual({ fonction: "Auditeur principal" });
  });

  it("edits names and email per right and sends only what changed", async () => {
    const { state, record } = serve(
      anAccount({ actions: { ...NO_ACTIONS, modifier_profil: true, modifier_courriel: false } }),
    );
    server.use(
      http.patch(ACCOUNT_URL, async ({ request }) => {
        await record(request);
        return HttpResponse.json(state.account);
      }),
    );
    const user = userEvent.setup();
    open("RAI", DELEGATE({ creer: true }));
    const email = await screen.findByRole("textbox", { name: "Courriel professionnel" });
    expect(email).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Direction" })).toBeDisabled();
    expect(screen.getByText(/Les champs grisés demandent un droit/)).toBeVisible();
    const first = screen.getByRole("textbox", { name: "Prénom" });
    await user.clear(first);
    await user.type(first, "Landri");
    await user.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
    await screen.findByText("Profil enregistré.");
    expect(state.sent[0]?.body).toEqual({ first_name: "Landri" });
  });

  it("validates the email before sending", async () => {
    const { state } = serve(anAccount());
    const user = userEvent.setup();
    open();
    const email = await screen.findByRole("textbox", { name: "Courriel professionnel" });
    await user.clear(email);
    await user.type(email, "pas-un-courriel");
    await user.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
    expect(await screen.findByText("Saisissez une adresse de courriel valide.")).toBeVisible();
    expect(email).toHaveAccessibleDescription("Saisissez une adresse de courriel valide.");
    expect(state.sent).toHaveLength(0);
  });

  it("shows no Keycloak or directory notion", async () => {
    serve(anAccount());
    open();
    await screen.findByRole("heading", { name: "Landry Kabore" });
    expect(document.body).not.toHaveTextContent(/keycloak|annuaire|synchronis/i);
    expect(screen.getByText("Création par l'administration")).toBeVisible();
  });
});
