import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { AUTH_URL, fakeMe, renderApp, serveSession, unauthorized } from "@/test/auth";
import { server, TEST_CSRF } from "@/test/msw";
import { allowSlowShell } from "@/test/shell";

allowSlowShell();

const T = fr.auth;

/** Connexion dont le mot de passe est accepté mais qui demande le code reçu par courriel. */
async function jusquAuCode() {
  server.use(http.post(`${AUTH_URL}/login/`, () => HttpResponse.json({ etape: "OTP", me: null })));
  const app = renderApp("/connexion");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText(T.identifiant), "rai");
  await user.type(screen.getByLabelText(T.password), "mot-de-passe-solide");
  await user.click(screen.getByRole("button", { name: T.login }));
  expect(await screen.findByRole("heading", { name: T.otpTitle })).toBeInTheDocument();
  return { ...app, user };
}

describe("OtpStep", () => {
  it("affiche l'étape du code, avec le focus sur le champ du code", async () => {
    await jusquAuCode();
    const code = screen.getByLabelText(T.otpCode);
    await waitFor(() => expect(code).toHaveFocus());
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    expect(code).toHaveAccessibleDescription(T.otpHelp);
    expect(screen.queryByLabelText(T.password)).not.toBeInTheDocument();
  });

  it("code valide : ouvre la session et envoie le jeton CSRF", async () => {
    let body: unknown = null;
    let csrf: string | null = null;
    server.use(
      http.post(`${AUTH_URL}/login/otp/`, async ({ request }) => {
        body = await request.json();
        csrf = request.headers.get("X-CSRFToken");
        serveSession();
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    const { router, user } = await jusquAuCode();
    await user.type(screen.getByLabelText(T.otpCode), "123456");
    await user.click(screen.getByRole("button", { name: T.otpSubmit }));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(body).toEqual({ code: "123456" });
    expect(csrf).toBe(TEST_CSRF);
  });

  it("code collé avec espaces (indentation du courriel) : accepté sans troncature", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${AUTH_URL}/login/otp/`, async ({ request }) => {
        body = await request.json();
        serveSession();
        return HttpResponse.json({ etape: "OK", me: fakeMe() });
      }),
    );
    const { user } = await jusquAuCode();
    const code = screen.getByLabelText(T.otpCode);
    await user.click(code);
    await user.paste("    654 321  ");
    expect(code).toHaveValue("654321");
    await user.click(screen.getByRole("button", { name: T.otpSubmit }));
    expect(await screen.findByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    expect(body).toEqual({ code: "654321" });
  });

  it("code refusé : message lié au champ et focus", async () => {
    server.use(http.post(`${AUTH_URL}/login/otp/`, () => unauthorized("Code invalide ou expiré.")));
    const { user } = await jusquAuCode();
    const code = screen.getByLabelText(T.otpCode);
    await user.type(code, "000000");
    await user.click(screen.getByRole("button", { name: T.otpSubmit }));
    await waitFor(() => expect(code).toHaveAccessibleDescription(`${T.otpHelp} ${T.otpInvalid}`));
    expect(code).toHaveAttribute("aria-invalid", "true");
    expect(code).toHaveFocus();
  });

  it("code refusé après Entrée : message annoncé (role=alert)", async () => {
    server.use(http.post(`${AUTH_URL}/login/otp/`, () => unauthorized("Code invalide ou expiré.")));
    const { user } = await jusquAuCode();
    await user.type(screen.getByLabelText(T.otpCode), "000000{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(T.otpInvalid);
    expect(screen.getByLabelText(T.otpCode)).toHaveFocus();
  });

  it("format invalide : erreur sans appel au serveur", async () => {
    let calls = 0;
    server.use(
      http.post(`${AUTH_URL}/login/otp/`, () => {
        calls += 1;
        return unauthorized();
      }),
    );
    const { user } = await jusquAuCode();
    await user.type(screen.getByLabelText(T.otpCode), "12a4");
    await user.click(screen.getByRole("button", { name: T.otpSubmit }));
    expect(await screen.findByText(T.otpFormat)).toBeInTheDocument();
    expect(calls).toBe(0);
  });

  it("« Recommencer la connexion » revient au formulaire d'identification", async () => {
    const { user } = await jusquAuCode();
    await user.click(screen.getByRole("button", { name: T.otpBack }));
    expect(await screen.findByLabelText(T.password)).toHaveValue("");
    expect(screen.getByRole("heading", { name: T.loginTitle })).toBeInTheDocument();
  });
});
