import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { pageOf } from "../testUtils";
import type { UtilisateurResume } from "../types";
import { UserPicker } from "./UserPicker";

const user = (id: number, nom: string): UtilisateurResume => ({
  id,
  username: nom.toLowerCase().replace(" ", "."),
  nom_complet: nom,
  role: "AUDITEUR",
  direction_code: "DAI",
  fonction: "Auditeur",
});

function Harness({ exclude }: { exclude?: string[] }) {
  const [value, setValue] = useState<string[]>([]);
  return (
    <UserPicker
      // eslint-disable-next-line jsx-a11y/aria-role -- `role` est ici le rôle métier, pas un rôle ARIA
      role="AUDITEUR"
      label="Auditeurs"
      value={value}
      onChange={setValue}
      exclude={exclude}
    />
  );
}

function setup(body: object, exclude?: string[]) {
  server.use(http.get(`${API_URL}/api/v1/users/`, () => HttpResponse.json(body)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Harness exclude={exclude} />
    </QueryClientProvider>,
  );
}

describe("UserPicker", () => {
  it("filters locally, selects and excludes users", async () => {
    setup(pageOf([user(1, "Awa Ouedraogo"), user(2, "Issa Traore"), user(3, "Fanta Sawadogo")]), [
      "3",
    ]);
    expect(await screen.findByLabelText(/Awa Ouedraogo/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Fanta Sawadogo/)).not.toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox"), "issa");
    expect(screen.queryByLabelText(/Awa Ouedraogo/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Issa Traore/));
    expect(screen.getByLabelText(/Issa Traore/)).toBeChecked();
    expect(screen.getByText("1 sélectionné(s)")).toBeInTheDocument();
  });

  it("warns when the list is incomplete", async () => {
    setup({ count: 500, next: null, previous: null, results: [user(1, "Awa Ouedraogo")] });
    expect(await screen.findByRole("alert")).toHaveTextContent("1 éléments sur 500");
  });
});
