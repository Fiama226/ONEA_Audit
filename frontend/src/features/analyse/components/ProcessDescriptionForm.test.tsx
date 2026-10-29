import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { aMission } from "@/features/missions/testUtils";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import type { DescriptionProcessus } from "../types";
import { ProcessDescriptionForm } from "./ProcessDescriptionForm";

const t = fr.analyseIII;
const PROCESS = { id: "88888888-8888-4888-8888-888888888888", code: "P-ACH", libelle: "Achats" };

function show(editable: boolean, description?: DescriptionProcessus) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ProcessDescriptionForm
        mission={aMission()}
        processus={PROCESS}
        description={description}
        editable={editable}
      />
    </QueryClientProvider>,
  );
}

const described: DescriptionProcessus = {
  id: "d-1",
  mission: "11111111-1111-4111-8111-111111111111",
  processus: PROCESS.id,
  processus_code: "P-ACH",
  processus_libelle: "Achats",
  typologie: "SUPPORT",
  categories_objectifs: ["CONFORMITE"],
  description: "Acheter",
  objectifs: "",
  indicateurs: "",
  sources: "",
  references_diagrammes: "",
  etape_close: false,
};

describe("ProcessDescriptionForm", () => {
  it("shows the to-describe badge and posts the upsert", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/process-descriptions/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(described, { status: 200 });
      }),
    );
    show(true);
    expect(screen.getByText(t.toDescribe)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(t.typology), "SUPPORT");
    await userEvent.click(screen.getByRole("checkbox", { name: "Conformité" }));
    await userEvent.type(screen.getByLabelText(t.narrative), "Acheter");
    await userEvent.click(screen.getByRole("button", { name: t.saveDescription }));
    await waitFor(() =>
      expect(body).toMatchObject({
        mission: "11111111-1111-4111-8111-111111111111",
        processus: PROCESS.id,
        typologie: "SUPPORT",
        categories_objectifs: ["CONFORMITE"],
        description: "Acheter",
      }),
    );
    expect(await screen.findByText(t.savedDescription)).toBeInTheDocument();
  });

  it("displays a server error on the field with aria-describedby", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/process-descriptions/`, () =>
        HttpResponse.json(
          { detail: "Refusé", errors: { description: ["Fenêtre close."] } },
          { status: 422 },
        ),
      ),
    );
    show(true);
    await userEvent.click(screen.getByRole("button", { name: t.saveDescription }));
    const field = screen.getByLabelText(t.narrative);
    expect(await screen.findByText("Fenêtre close.")).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAttribute("aria-describedby");
    await waitFor(() => expect(field).toHaveFocus());
  });

  it("focuses the first category checkbox on a categories server error", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/process-descriptions/`, () =>
        HttpResponse.json(
          { detail: "Refusé", errors: { categories_objectifs: ["Catégorie invalide."] } },
          { status: 422 },
        ),
      ),
    );
    show(true);
    await userEvent.click(screen.getByRole("button", { name: t.saveDescription }));
    expect(await screen.findByText("Catégorie invalide.")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Opérationnels" })).toHaveFocus(),
    );
  });

  it("is plain text when read-only", () => {
    show(false, described);
    expect(screen.getByText(t.described)).toBeInTheDocument();
    expect(screen.getByText("Support")).toBeInTheDocument();
    expect(screen.getByText("Conformité")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
