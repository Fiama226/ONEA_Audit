import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { anAccount, aTemporaryPassword, rights } from "../testUtils";
import { UserListActions } from "./UserListActions";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const CREATE_URL = `${API_URL}/api/v1/user-accounts/`;
const PASSWORD = "Tmp-9f3K-q7Lm-2xWz";

function renderActions(role: Role = "ADMIN", me = {}) {
  server.use(
    http.get(`${API_URL}/api/v1/directions/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
  return renderWithAuth(<UserListActions />, role, "/administration/utilisateurs", me);
}

/** Sert la création ; renvoie les corps reçus. */
function serveCreate(response = aTemporaryPassword()) {
  const bodies: unknown[] = [];
  server.use(
    http.post(CREATE_URL, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(response, {
        status: 201,
        headers: { "Cache-Control": "no-store" },
      });
    }),
  );
  return bodies;
}

async function openForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Nouvel agent" }));
  return screen.findByRole("dialog", { name: "Nouvel agent" });
}

describe("UserListActions — Nouvel agent", () => {
  it("offers creation and CSV import to an ADMIN", () => {
    renderActions("ADMIN");
    expect(screen.getByRole("button", { name: "Nouvel agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importer un fichier CSV" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /annuaire/i })).not.toBeInTheDocument();
  });

  it("offers creation but not the CSV import to a delegate allowed to create", () => {
    renderActions("RAI", { gestion_comptes: rights({ creer: true }) });
    expect(screen.getByRole("button", { name: "Nouvel agent" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Importer un fichier CSV" })).toBeNull();
  });

  it("offers nothing to a delegate without the create right", () => {
    renderActions("RAI", { gestion_comptes: rights({ desactiver: true }) });
    expect(screen.queryByRole("button", { name: "Nouvel agent" })).toBeNull();
  });

  it("selects no role by default and requires one", async () => {
    const bodies = serveCreate();
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    const role = within(dialog).getByRole("combobox", { name: "Rôle" });
    expect(role).toHaveValue("");
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "ouedraogo.a");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    expect(await within(dialog).findByText("Choisissez le rôle de l'agent.")).toBeVisible();
    expect(role).toHaveAccessibleDescription(/Choisissez le rôle de l'agent\./);
    expect(role).toHaveFocus();
    expect(bodies).toHaveLength(0);
  });

  it("checks the welcome email by default and only offers AUDITEUR and AUDITE to a delegate", async () => {
    const user = userEvent.setup();
    renderActions("RAI", { gestion_comptes: rights({ creer: true }) });
    const dialog = await openForm(user);
    expect(
      within(dialog).getByRole("checkbox", { name: "Envoyer le courriel de bienvenue" }),
    ).toBeChecked();
    const options = within(within(dialog).getByRole("combobox", { name: "Rôle" }))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["Choisir un rôle", "Auditeur", "Audité"]);
  });

  it("creates without email and shows the temporary password once", async () => {
    const bodies = serveCreate();
    const user = userEvent.setup();
    const { client } = renderActions();
    const dialog = await openForm(user);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "ouedraogo.a");
    await user.type(within(dialog).getByRole("textbox", { name: "Prénom" }), "Awa");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITEUR");
    await user.click(
      within(dialog).getByRole("checkbox", { name: "Envoyer le courriel de bienvenue" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));

    expect(await within(dialog).findByRole("heading", { name: "Compte créé" })).toBeVisible();
    expect(bodies).toEqual([
      expect.objectContaining({
        username: "ouedraogo.a",
        first_name: "Awa",
        role: "AUDITEUR",
        envoyer_courriel: false,
      }),
    ]);
    expect(within(dialog).getByText(PASSWORD)).toBeVisible();
    expect(within(dialog).getByText(/il ne sera plus jamais affiché/)).toBeVisible();
    expect(
      within(dialog).getByRole("link", { name: "Ouvrir la fiche de l'agent" }),
    ).toHaveAttribute("href", "/administration/utilisateurs/7");

    await user.click(within(dialog).getByRole("button", { name: "Copier le mot de passe" }));
    expect(await navigator.clipboard.readText()).toBe(PASSWORD);
    expect(
      await within(dialog).findByText("Mot de passe copié dans le presse-papiers."),
    ).toBeVisible();

    // Ni Échap ni un clic à l'extérieur ne ferment la fenêtre tant que le mot de passe est affiché.
    await user.keyboard("{Escape}");
    fireEvent.pointerDown(document.body);
    expect(screen.getByRole("dialog", { name: "Nouvel agent" })).toBeInTheDocument();
    expect(within(dialog).getByText(PASSWORD)).toBeVisible();

    await user.click(
      within(dialog).getByRole("button", { name: "J'ai noté le mot de passe, fermer" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // Focus rendu au déclencheur ; le mot de passe n'est plus ni dans le DOM ni dans les caches.
    expect(screen.getByRole("button", { name: "Nouvel agent" })).toHaveFocus();
    expect(document.body).not.toHaveTextContent(PASSWORD);
    const cached = JSON.stringify([
      client
        .getQueryCache()
        .getAll()
        .map((q) => q.state.data),
      client
        .getMutationCache()
        .getAll()
        .map((m) => [m.state.data, m.state.variables]),
    ]);
    expect(cached).not.toContain(PASSWORD);

    // Rouvert : formulaire vierge, aucun mot de passe.
    const again = await openForm(user);
    expect(within(again).getByRole("textbox", { name: "Identifiant" })).toHaveValue("");
    expect(within(again).queryByText(PASSWORD)).toBeNull();
  });

  it("says the welcome email was queued and shows no password when it was sent", async () => {
    serveCreate(aTemporaryPassword({ courriel_envoye: true, mot_de_passe_temporaire: null }));
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "kabore.l");
    await user.type(
      within(dialog).getByRole("textbox", { name: "Courriel professionnel" }),
      "l.kabore@onea.bf",
    );
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITEUR");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    expect(
      await within(dialog).findByText(/a été mis en file d'envoi pour l\.kabore@onea\.bf/),
    ).toBeInTheDocument();
    expect(within(dialog).queryByText("Mot de passe temporaire")).toBeNull();
  });

  it("shows the password when the email was asked but could not be sent", async () => {
    const bodies = serveCreate(
      aTemporaryPassword({ compte: anAccount({ email: "" }), courriel_envoye: false }),
    );
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "kabore.l");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "DG");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    expect(await within(dialog).findByText(PASSWORD)).toBeVisible();
    expect(
      within(dialog).getByText(/Aucun courriel de bienvenue n'a été mis en file d'envoi/),
    ).toBeVisible();
    expect(bodies[0]).toMatchObject({ envoyer_courriel: true, role: "DG" });
  });

  it("ties a server error to its field", async () => {
    server.use(
      http.post(CREATE_URL, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { username: ["Cet identifiant existe déjà."] } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    const username = within(dialog).getByRole("textbox", { name: "Identifiant" });
    await user.type(username, "kabore.l");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITE");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    expect(await within(dialog).findByText("Cet identifiant existe déjà.")).toBeVisible();
    expect(username).toHaveAccessibleDescription(/Cet identifiant existe déjà\./);
  });

  it("has no accessibility violation, form and password result", async () => {
    serveCreate();
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "a.b");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITE");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    await within(dialog).findByText(PASSWORD);
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
    await user.click(
      within(dialog).getByRole("button", { name: "J'ai noté le mot de passe, fermer" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Nouvel agent" })).toHaveFocus();
  });

  it("cannot be closed while the creation is pending", async () => {
    let release: () => void = () => {};
    server.use(
      http.post(CREATE_URL, async () => {
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        return HttpResponse.json(aTemporaryPassword(), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "a.b");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITE");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    expect(await within(dialog).findByRole("button", { name: "Création en cours" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Annuler" })).toBeDisabled();
    await user.keyboard("{Escape}");
    fireEvent.pointerDown(document.body);
    expect(screen.getByRole("dialog", { name: "Nouvel agent" })).toBeInTheDocument();
    release();
    expect(await within(dialog).findByText(PASSWORD)).toBeVisible();
  });

  it("closes normally (Escape) when the password went by email", async () => {
    serveCreate(aTemporaryPassword({ courriel_envoye: true, mot_de_passe_temporaire: null }));
    const user = userEvent.setup();
    renderActions();
    const dialog = await openForm(user);
    await user.type(within(dialog).getByRole("textbox", { name: "Identifiant" }), "a.b");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Rôle" }), "AUDITE");
    await user.click(within(dialog).getByRole("button", { name: "Créer le compte" }));
    await within(dialog).findByRole("heading", { name: "Compte créé" });
    expect(within(dialog).getByRole("button", { name: "Fermer" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
