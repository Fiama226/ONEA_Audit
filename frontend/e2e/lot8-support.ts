import { expect, type Browser, type Page } from "@playwright/test";
import { devToken } from "./api";

// Helpers shared by the lot 8 specs (follow-up, decision queue, search). Nothing is cleaned up:
// the database is discarded at the end of the run (scripts/e2e.sh).
const PASSWORD = "onea2026";
const WEB_PORT = process.env.WEB_PORT ?? "5174";
export const BASE = `http://localhost:${WEB_PORT}`;
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
/** HTTP API of Mailpit (dev stack); the mail check is skipped when it is unreachable. */
export const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

export async function logIn(page: Page, username: string) {
  await page.goto("/");
  const loginButton = page.getByRole("button", { name: "Se connecter" });
  await expect(loginButton).toBeEnabled();
  await loginButton.click();
  await page.waitForURL(/\/realms\/onea\/protocol\/openid-connect\/auth/);
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${BASE}/`);
}

/** A fresh browser context per account: the Keycloak session cookie is never shared. */
export async function sessionOf(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE, locale: "fr-FR" });
  const page = await context.newPage();
  await logIn(page, username);
  return page;
}

export type FollowUpAction = { id: string; action_libelle: string; statut: string };

/**
 * First follow-up action in the given status, as seen by the RAI, or `null` when the stack holds
 * no follow-up data. The lot 8 journeys need a broadcast mission with its action plan: there is
 * no demonstration seed for the follow-up yet, so the specs skip (with the reason) instead of failing.
 */
export async function firstFollowUpAction(statut: string): Promise<FollowUpAction | null> {
  const token = await devToken("rai");
  const response = await fetch(`${API}/api/v1/follow-up/actions/?statut=${statut}&page_size=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;
  const body = (await response.json()) as { results: FollowUpAction[] };
  return body.results[0] ?? null;
}

/** Messages of Mailpit mentioning `text`, or `null` when Mailpit is not reachable. */
export async function mailpitMessages(text: string): Promise<number | null> {
  try {
    const response = await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(text)}`);
    if (!response.ok) return null;
    return ((await response.json()) as { messages_count: number }).messages_count;
  } catch {
    return null;
  }
}
