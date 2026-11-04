// Run against a throw-away database (scripts/e2e.sh): no cleanup, no SQL. Accounts come from
// `manage.py creer_comptes_e2e`; API calls go through a session cookie (see ./session.ts).
import type { ApiSession } from "./session";

/** Unique per run (set once by playwright.config.ts, inherited by the workers). */
export const E2E_RUN_ID = process.env.E2E_RUN_ID ?? "local";

type Page<T> = { count: number; results: T[] };

// ---------------------------------------------------------------------------- missions (lot 3)

/** Process and direction used by the mission flow (created through the API when missing). */
export const E2E_MISSION_PROCESS_CODE = "ZZM";
export const E2E_MISSION_PROCESS_LABEL = "Processus de test missions";
export const E2E_MISSION_YEAR = 2097;
/** Direction of the e2e account `audite1` (creer_comptes_e2e), proposed as default auditee. */
export const E2E_AUDITEE_DIRECTION = "DEX";
/** Every e2e mission title starts with this run-specific prefix. */
export const E2E_MISSION_PREFIX = `E2E ${E2E_RUN_ID} — `;

/**
 * A mission can only be created on a validated risk map. If none exists, creates the direction
 * DEX and the process ZZM when missing, then the map 2097 with one risk, validated by the API.
 * Idempotent; the database is discarded at the end of the run.
 */
export async function ensureValidatedRiskMap(session: ApiSession): Promise<void> {
  const directions = await session.get<Page<{ code: string }>>(
    `/api/v1/directions/?q=${E2E_AUDITEE_DIRECTION}`,
  );
  if (!directions.results.some((d) => d.code === E2E_AUDITEE_DIRECTION)) {
    await session.send("POST", "/api/v1/directions/", {
      code: E2E_AUDITEE_DIRECTION,
      libelle: "Direction de l'exploitation (e2e)",
      type: "DIRECTION",
    });
  }
  const processes = await session.get<Page<{ id: string; code: string }>>(
    `/api/v1/processes/?q=${E2E_MISSION_PROCESS_CODE}`,
  );
  let process = processes.results.find((p) => p.code === E2E_MISSION_PROCESS_CODE);
  if (!process) {
    process = await session.send<{ id: string; code: string }>("POST", "/api/v1/processes/", {
      code: E2E_MISSION_PROCESS_CODE,
      libelle: E2E_MISSION_PROCESS_LABEL,
      famille: "SUPPORT",
    });
  }
  const maps = await session.get<Page<{ statut: string }>>("/api/v1/risk-maps/?statut=VALIDEE");
  if (maps.results.some((m) => m.statut === "VALIDEE")) return;
  const map = await session.send<{ id: string }>("POST", "/api/v1/risk-maps/", {
    annee: E2E_MISSION_YEAR,
    libelle: "Cartographie de test missions",
  });
  await session.send("POST", "/api/v1/risks/", {
    version: map.id,
    processus: process.id,
    libelle: "Risque de référence e2e missions",
    probabilite: 2,
    impact: 2,
  });
  await session.send("POST", `/api/v1/risk-maps/${map.id}/validate/`);
}
