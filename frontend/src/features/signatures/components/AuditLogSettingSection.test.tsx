import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import type { ReglageJournal } from "../adminApi";
import { AuditLogSettingSection } from "./AuditLogSettingSection";

const URL = `${API_URL}/api/v1/audit-log-settings/`;
const LABEL = "Contenu des missions visible par l'administrateur dans la piste d'audit";

function aSetting(overrides: Partial<ReglageJournal> = {}): ReglageJournal {
  return {
    valeur: "COMPLET",
    valeur_libelle: "Complet",
    modifie_le: null,
    modifie_par: null,
    ...overrides,
  };
}

function renderSection(role: Role = "ADMIN") {
  return renderRoutes([{ path: "*", element: <AuditLogSettingSection /> }], role);
}

describe("AuditLogSettingSection", () => {
  it("lets the admin switch to masked mode after confirmation", async () => {
    let body: unknown = null;
    server.use(
      http.get(URL, () => HttpResponse.json(aSetting())),
      http.patch(URL, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aSetting({ valeur: "MASQUE" }));
      }),
    );
    const { container } = renderSection();
    const select = await screen.findByRole("combobox", { name: LABEL });
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
    await userEvent.selectOptions(select, "MASQUE");
    expect(body).toBeNull();
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Modifier le réglage" }));
    await screen.findByRole("combobox", { name: LABEL });
    expect(body).toEqual({ valeur: "MASQUE" });
  });

  it("is read-only for the RAI", async () => {
    server.use(http.get(URL, () => HttpResponse.json(aSetting())));
    renderSection("RAI");
    expect(await screen.findByText(/Lecture seule/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows the server field error and keeps the dialog open", async () => {
    server.use(
      http.get(URL, () => HttpResponse.json(aSetting())),
      http.patch(URL, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { valeur: ["Valeur inconnue."] } },
          { status: 422 },
        ),
      ),
    );
    renderSection();
    await userEvent.selectOptions(await screen.findByRole("combobox"), "MASQUE");
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Modifier le réglage" }));
    expect(await within(dialog).findByText("Valeur inconnue.")).toBeInTheDocument();
  });

  it("shows an error, not a default value, when loading fails", async () => {
    server.use(http.get(URL, () => HttpResponse.json({ detail: "Erreur" }, { status: 500 })));
    renderSection();
    expect(
      await screen.findByText("Impossible de charger le réglage de la piste d'audit."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
