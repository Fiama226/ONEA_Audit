import { safeReturnPath } from "./safePath";

/** Routes of the login and password pages (declared in routes.tsx). */
export const AUTH_PATHS = {
  login: "/connexion",
  forgot: "/mot-de-passe-oublie",
  reset: "/mot-de-passe/reinitialiser",
  change: "/mot-de-passe/changer",
} as const;

/** Router state `notice` set after a successful password change (read by the app shell). */
export const PASSWORD_CHANGED_NOTICE = "password-changed";

/** Router state field `name` when it is a string, else undefined. */
export function stateField(state: unknown, name: string): string | undefined {
  if (typeof state === "object" && state !== null && name in state) {
    const value = (state as Record<string, unknown>)[name];
    return typeof value === "string" ? value : undefined;
  }
  return undefined;
}

/** Validated return path carried in the router state (`from`), "/" by default. */
export function returnPathOf(state: unknown): string {
  return safeReturnPath(stateField(state, "from"));
}
