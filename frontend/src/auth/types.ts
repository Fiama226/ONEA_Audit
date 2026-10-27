import type { components } from "../api/schema";

export type Me = components["schemas"]["Me"];
export type Role = components["schemas"]["RoleEnum"];

/** Runtime list of roles; the type check below keeps it in sync with the generated RoleEnum. */
export const ROLES = ["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"] as const;

type Equals<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
  ? true
  : false;
// Compile error if ROLES and RoleEnum diverge (in either direction).
const rolesMatchSchema: Equals<(typeof ROLES)[number], Role> = true;
void rolesMatchSchema;

/** Rôle appliqué par défaut quand le serveur renvoie une valeur inconnue (moindre privilège). */
export const DEFAULT_ROLE: Role = "AUDITE";

export function toRole(value: unknown): Role {
  return ROLES.find((r) => r === value) ?? DEFAULT_ROLE;
}

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "error";
