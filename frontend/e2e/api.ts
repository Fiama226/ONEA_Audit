import { execFileSync } from "node:child_process";

// Dev stack only. The Keycloak client "onea-dev-cli" is the only one with the password grant
// (docker/keycloak/realm-onea.json); the API runs on the Django dev server.
const KEYCLOAK = process.env.E2E_OIDC_AUTHORITY ?? "http://localhost:8080/realms/onea";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "onea2026";

/** Test data created by the referentiel flow (nothing else is ever touched). */
export const E2E_PROCESS_CODE = "ZZE";
export const E2E_YEARS = [2098, 2099];

export async function devToken(username: string): Promise<string> {
  const response = await fetch(`${KEYCLOAK}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "password",
      client_id: "onea-dev-cli",
      username,
      password: PASSWORD,
      scope: "openid",
    }),
  });
  if (!response.ok) throw new Error(`Keycloak token request failed: ${response.status}`);
  return ((await response.json()) as { access_token: string }).access_token;
}

async function get<T>(token: string, path: string): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`GET ${path} failed: ${response.status}`);
  return (await response.json()) as T;
}

type Page<T> = { count: number; results: T[] };

/**
 * A validated risk map is frozen and cannot be deleted through the API (by design), so the
 * e2e data is soft-deleted directly in the dev database (same effect as the API's soft
 * delete: `deleted_at` is set, which also frees the unique year and process code). The audit
 * log entries of the test run are kept. Requires the dev compose stack (service "db"); the
 * compose project is picked up from COMPOSE_PROJECT_NAME when it is set.
 */
function softDeleteInDatabase(): void {
  const years = E2E_YEARS.join(",");
  const code = E2E_PROCESS_CODE;
  const sql = `
    UPDATE referentiel_risque SET deleted_at = now()
      WHERE deleted_at IS NULL AND (
        version_id IN (SELECT id FROM referentiel_cartographieversion WHERE annee IN (${years}))
        OR processus_id IN (SELECT id FROM referentiel_processus WHERE code = '${code}'));
    UPDATE referentiel_cartographieversion SET deleted_at = now()
      WHERE deleted_at IS NULL AND annee IN (${years});
    UPDATE referentiel_objetauditable SET deleted_at = now()
      WHERE deleted_at IS NULL AND processus_id IN
        (SELECT id FROM referentiel_processus WHERE code = '${code}');
    UPDATE referentiel_processus SET deleted_at = now()
      WHERE deleted_at IS NULL AND code = '${code}';`;
  execFileSync(
    "docker",
    [
      "compose",
      "--env-file",
      "../.env",
      "-f",
      "../docker/compose.yml",
      "-f",
      "../docker/compose.dev.yml",
      "exec",
      "-T",
      "db",
      "psql",
      "-v",
      "ON_ERROR_STOP=1",
      "-U",
      process.env.POSTGRES_USER ?? "onea",
      "-d",
      process.env.POSTGRES_DB ?? "onea",
    ],
    { input: sql, stdio: ["pipe", "pipe", "inherit"] },
  );
}

/** Removes the e2e risk maps (2098, 2099) and the process ZZE, then checks nothing is left. */
export async function cleanupReferentiel(token: string): Promise<void> {
  softDeleteInDatabase();
  for (const annee of E2E_YEARS) {
    const maps = await get<Page<unknown>>(token, `/api/v1/risk-maps/?annee=${annee}`);
    if (maps.count !== 0) throw new Error(`Cleanup failed: risk map ${annee} still exists`);
  }
  const processes = await get<Page<unknown>>(token, `/api/v1/processes/?q=${E2E_PROCESS_CODE}`);
  if (processes.count !== 0) throw new Error("Cleanup failed: process ZZE still exists");
}
