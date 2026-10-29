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
 * Runs SQL in the dev Postgres through the compose service "db" (psql). Refused unless
 * E2E_ALLOW_DB_CLEANUP=1 (lesson M8: never write to a database by accident). Set
 * E2E_DB_CONTAINER=<name> to target a given running container with `docker exec` instead of
 * compose (e.g. a second stack), and POSTGRES_DB to pick the database it cleans.
 */
function runSql(sql: string): void {
  if (process.env.E2E_ALLOW_DB_CLEANUP !== "1") {
    throw new Error(
      "e2e cleanup writes SQL to the dev database: set E2E_ALLOW_DB_CLEANUP=1 to allow it.",
    );
  }
  const psql = [
    "psql",
    "-v",
    "ON_ERROR_STOP=1",
    "-U",
    process.env.POSTGRES_USER ?? "onea",
    "-d",
    process.env.POSTGRES_DB ?? "onea",
  ];
  const container = process.env.E2E_DB_CONTAINER;
  const args = container
    ? ["exec", "-i", container, ...psql]
    : [
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
        ...psql,
      ];
  execFileSync("docker", args, { input: sql, stdio: ["pipe", "pipe", "inherit"] });
}

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
  runSql(sql);
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

// ---------------------------------------------------------------------------- missions (lot 3)

/** Process and direction used by the mission flow (created through the API when missing). */
export const E2E_MISSION_PROCESS_CODE = "ZZM";
export const E2E_MISSION_PROCESS_LABEL = "Processus de test missions";
export const E2E_MISSION_YEAR = 2097;
/** Direction of the dev user `audite1` (realm attribute), proposed as default auditee. */
export const E2E_AUDITEE_DIRECTION = "DEX";
/** Every e2e mission title starts with this prefix; cleanup only touches these. */
export const E2E_MISSION_PREFIX = "E2E — ";

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
 * Idempotent; the data is kept (a validated map cannot be deleted through the API).
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

/**
 * Soft-deletes (same effect as the API's soft delete) the e2e missions, titles starting with
 * "E2E — ", and their children. Audit-log entries are kept. Guarded by E2E_ALLOW_DB_CLEANUP=1.
 */
export async function cleanupMissions(token: string): Promise<void> {
  const mine = `SELECT id FROM missions_mission WHERE titre LIKE '${E2E_MISSION_PREFIX}%'`;
  runSql(`
    UPDATE missions_declarationindependance SET deleted_at = now() WHERE deleted_at IS NULL
      AND affectation_id IN (SELECT id FROM missions_affectationmission WHERE mission_id IN (${mine}));
    UPDATE missions_evenementetape SET deleted_at = now() WHERE deleted_at IS NULL
      AND etape_id IN (SELECT id FROM missions_etapemission WHERE mission_id IN (${mine}));
    UPDATE missions_entretien SET deleted_at = now() WHERE deleted_at IS NULL AND mission_id IN (${mine});
    UPDATE missions_reunion SET deleted_at = now() WHERE deleted_at IS NULL AND mission_id IN (${mine});
    UPDATE missions_risquemission SET deleted_at = now() WHERE deleted_at IS NULL AND mission_id IN (${mine});
    UPDATE missions_affectationmission SET deleted_at = now() WHERE deleted_at IS NULL AND mission_id IN (${mine});
    UPDATE missions_etapemission SET deleted_at = now() WHERE deleted_at IS NULL AND mission_id IN (${mine});
    UPDATE missions_mission SET deleted_at = now()
      WHERE deleted_at IS NULL AND titre LIKE '${E2E_MISSION_PREFIX}%';`);
  const left = await get<Page<unknown>>(
    token,
    `/api/v1/missions/?q=${encodeURIComponent(E2E_MISSION_PREFIX.trim())}`,
  );
  if (left.count !== 0) throw new Error("Cleanup failed: e2e missions still exist");
}
