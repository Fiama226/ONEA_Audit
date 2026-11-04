import {
  expect,
  request,
  type APIRequestContext,
  type APIResponse,
  type Browser,
  type Page,
} from "@playwright/test";

// Connexion des specs par le vrai formulaire (/connexion) et par l'API de session (cookie +
// jeton CSRF). Les comptes sont créés par `manage.py creer_comptes_e2e` (scripts/e2e.sh ou
// e2e.ps1) avec le mot de passe E2E_PASSWORD, sans changement forcé : voir le docstring de la
// commande, réservée à la base jetable onea_e2e_<nombre>.
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "Onea-e2e-2026-pwd";
export const BASE = `http://localhost:${process.env.WEB_PORT ?? "5174"}`;

/** Ouvre une session dans le navigateur : formulaire /connexion, identifiant + mot de passe. */
export async function logIn(page: Page, username: string): Promise<void> {
  await page.goto("/connexion");
  await page.getByLabel("Identifiant ou courriel professionnel").fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await page.waitForURL(`${BASE}/`);
}

/** Un contexte de navigateur neuf par compte : les cookies de session ne sont jamais partagés. */
export async function sessionOf(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE, locale: "fr-FR" });
  const page = await context.newPage();
  await logIn(page, username);
  return page;
}

type Json = Record<string, unknown> | unknown[];

/** Session d'API d'un compte (cookie de session + jeton CSRF), jointe via l'origine de Vite. */
export class ApiSession {
  private constructor(
    private readonly context: APIRequestContext,
    private csrf: string,
  ) {}

  /** Connexion : jeton CSRF, puis POST /auth/login/ (Referer exigé), puis jeton renouvelé. */
  static async login(username: string): Promise<ApiSession> {
    const context = await request.newContext({
      baseURL: BASE,
      extraHTTPHeaders: { Referer: BASE },
    });
    const csrf = await ApiSession.fetchCsrf(context);
    const response = await context.post("/api/v1/auth/login/", {
      headers: { "X-CSRFToken": csrf },
      data: { identifiant: username, mot_de_passe: E2E_PASSWORD },
    });
    if (!response.ok()) {
      throw new Error(`login ${username} failed: ${response.status()} ${await response.text()}`);
    }
    const body = (await response.json()) as { etape?: string };
    if (body.etape !== "OK") throw new Error(`login ${username}: step ${String(body.etape)}`);
    // Django renouvelle le jeton CSRF à la connexion.
    return new ApiSession(context, await ApiSession.fetchCsrf(context));
  }

  private static async fetchCsrf(context: APIRequestContext): Promise<string> {
    const response = await context.get("/api/v1/auth/csrf/");
    expect(response.ok()).toBe(true);
    return ((await response.json()) as { csrf_token: string }).csrf_token;
  }

  /** GET brut (statut laissé à l'appelant : les journeys sautent si la ressource est absente). */
  raw(path: string): Promise<APIResponse> {
    return this.context.get(path);
  }

  async get<T>(path: string): Promise<T> {
    const response = await this.context.get(path);
    if (!response.ok()) throw new Error(`GET ${path} failed: ${response.status()}`);
    return (await response.json()) as T;
  }

  /** Écriture (POST/PATCH/...) avec X-CSRFToken ; la réponse est renvoyée sans contrôle. */
  write(
    method: "POST" | "PATCH" | "PUT" | "DELETE",
    path: string,
    body?: Json,
  ): Promise<APIResponse> {
    return this.context.fetch(path, {
      method,
      headers: { "X-CSRFToken": this.csrf },
      data: body,
    });
  }

  async send<T>(
    method: "POST" | "PATCH" | "PUT" | "DELETE",
    path: string,
    body?: Json,
  ): Promise<T> {
    const response = await this.write(method, path, body);
    if (!response.ok()) {
      throw new Error(`${method} ${path} failed: ${response.status()} ${await response.text()}`);
    }
    return (response.status() === 204 ? undefined : await response.json()) as T;
  }

  dispose(): Promise<void> {
    return this.context.dispose();
  }
}
