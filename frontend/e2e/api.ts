// Run against a throw-away database (scripts/e2e.sh): no cleanup, no SQL. The Keycloak client
// "onea-dev-cli" is the only one with the password grant (docker/keycloak/realm-onea.json).
const KEYCLOAK = process.env.E2E_OIDC_AUTHORITY ?? "http://localhost:8080/realms/onea";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "onea2026";

/** Unique per run (set once by playwright.config.ts, inherited by the workers). */
export const E2E_RUN_ID = process.env.E2E_RUN_ID ?? "local";

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

// ---------------------------------------------------------------------------- missions (lot 3)

/** Process and direction used by the mission flow (created through the API when missing). */
export const E2E_MISSION_PROCESS_CODE = "ZZM";
export const E2E_MISSION_PROCESS_LABEL = "Processus de test missions";
export const E2E_MISSION_YEAR = 2097;
/** Direction of the dev user `audite1` (realm attribute), proposed as default auditee. */
export const E2E_AUDITEE_DIRECTION = "DEX";
/** Every e2e mission title starts with this run-specific prefix. */
export const E2E_MISSION_PREFIX = `E2E ${E2E_RUN_ID} — `;

async function send<T>(token: string, method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} failed: ${response.status} ${await response.text()}`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Creates the Django user of each dev account (first authenticated call to /me/). */
export async function provisionUsers(): Promise<void> {
  for (const username of ["rai", "auditeur1", "audite1"]) {
    await get(await devToken(username), "/api/v1/me/");
  }
}

/**
 * A mission can only be created on a validated risk map. If none exists, creates the direction
 * DEX and the process ZZM when missing, then the map 2097 with one risk, validated by the API.
 * Idempotent; the database is discarded at the end of the run.
 */
export async function ensureValidatedRiskMap(token: string): Promise<void> {
  const directions = await get<Page<{ code: string }>>(
    token,
    `/api/v1/directions/?q=${E2E_AUDITEE_DIRECTION}`,
  );
  if (!directions.results.some((d) => d.code === E2E_AUDITEE_DIRECTION)) {
    await send(token, "POST", "/api/v1/directions/", {
      code: E2E_AUDITEE_DIRECTION,
      libelle: "Direction de l'exploitation (e2e)",
      type: "DIRECTION",
    });
  }
  const processes = await get<Page<{ id: string; code: string }>>(
    token,
    `/api/v1/processes/?q=${E2E_MISSION_PROCESS_CODE}`,
  );
  let process = processes.results.find((p) => p.code === E2E_MISSION_PROCESS_CODE);
  if (!process) {
    process = await send<{ id: string; code: string }>(token, "POST", "/api/v1/processes/", {
      code: E2E_MISSION_PROCESS_CODE,
      libelle: E2E_MISSION_PROCESS_LABEL,
      famille: "SUPPORT",
    });
  }
  const maps = await get<Page<{ statut: string }>>(token, "/api/v1/risk-maps/?statut=VALIDEE");
  if (maps.results.some((m) => m.statut === "VALIDEE")) return;
  const map = await send<{ id: string }>(token, "POST", "/api/v1/risk-maps/", {
    annee: E2E_MISSION_YEAR,
    libelle: "Cartographie de test missions",
  });
  await send(token, "POST", "/api/v1/risks/", {
    version: map.id,
    processus: process.id,
    libelle: "Risque de référence e2e missions",
    probabilite: 2,
    impact: 2,
  });
  await send(token, "POST", `/api/v1/risk-maps/${map.id}/validate/`);
}
