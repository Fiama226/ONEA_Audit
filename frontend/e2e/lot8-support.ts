import { ApiSession } from "./session";

export { BASE, logIn, sessionOf } from "./session";

// Helpers shared by the lot 8 specs (follow-up, decision queue, search). Nothing is cleaned up:
// the database is discarded at the end of the run (scripts/e2e.sh).
/** HTTP API of Mailpit (dev stack); the mail check is skipped when it is unreachable. */
export const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

export type FollowUpAction = { id: string; action_libelle: string; statut: string };

/**
 * First follow-up action in the given status, as seen by the RAI, or `null` when the stack holds
 * no follow-up data. The lot 8 journeys need a broadcast mission with its action plan: there is
 * no demonstration seed for the follow-up yet, so the specs skip (with the reason) instead of failing.
 */
export async function firstFollowUpAction(statut: string): Promise<FollowUpAction | null> {
  const rai = await ApiSession.login("rai");
  try {
    const response = await rai.raw(`/api/v1/follow-up/actions/?statut=${statut}&page_size=1`);
    if (!response.ok()) return null;
    const body = (await response.json()) as { results: FollowUpAction[] };
    return body.results[0] ?? null;
  } finally {
    await rai.dispose();
  }
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
