import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, renderApp } from "@/test/auth";
import { server, TEST_CSRF } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

const T = fr.auth;

async function demander(identifiant: string) {
  const app = renderApp("/mot-de-passe-oublie");
  const user = userEvent.setup();
  expect(await screen.findByRole("heading", { name: T.forgotTitle })).toBeInTheDocument();
  if (identifiant) await user.type(screen.getByLabelText(T.identifiant), identifiant);
  await user.click(screen.getByRole("button", { name: T.forgotSubmit }));
  return { ...app, user };
}

describe("ForgotPasswordPage", () => {
  it("envoie l'identifiant avec CSRF et affiche la confirmation neutre", async () => {
    let body: unknown = null;
    let csrf: string | null = null;
    server.use(
      http.post(`${AUTH_URL}/password/forgot/`, async ({ request }) => {
        body = await request.json();
        csrf = request.headers.get("X-CSRFToken");
        return HttpResponse.json({ detail: "Texte du serveur." }, { status: 202 });
      }),
    );
    await demander("agent@onea.bf");
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(T.forgotSent);
    await waitFor(() => expect(status).toHaveFocus());
    expect(body).toEqual({ identifiant: "agent@onea.bf" });
    expect(csrf).toBe(TEST_CSRF);
    expect(screen.getByRole("link", { name: T.forgotEnterCode })).toHaveAttribute(
      "href",
      "/mot-de-passe/reinitialiser",
    );
  });

  it.each([
    ["202", () => HttpResponse.json({ detail: "x" }, { status: 202 })],
    ["429", () => HttpResponse.json({ detail: "Trop de requêtes.", errors: {} }, { status: 429 })],
    ["400", () => HttpResponse.json({ detail: "Données invalides.", errors: {} }, { status: 400 })],
    ["500", () => HttpResponse.json({}, { status: 500 })],
  ])("réponse %s : toujours la même confirmation", async (_status, respond) => {
    server.use(http.post(`${AUTH_URL}/password/forgot/`, respond));
    await demander("inconnu");
    expect(await screen.findByRole("status")).toHaveTextContent(T.forgotSent);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("identifiant vide : erreur liée au champ", async () => {
    await demander("");
    const champ = screen.getByLabelText(T.identifiant);
    await waitFor(() => expect(champ).toHaveFocus());
    expect(champ).toHaveAccessibleDescription(T.identifiantRequired);
  });

  it("serveur injoignable : message réseau pour réessayer", async () => {
    server.use(http.post(`${AUTH_URL}/password/forgot/`, () => HttpResponse.error()));
    await demander("agent@onea.bf");
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.errors.network);
  });
});
