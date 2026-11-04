import type { components } from "../api/schema";

// `otp_connexion_actif` is served by /api/v1/auth/ but not yet in the committed schema.d.ts
// (regenerated in a later task); the intersection keeps it typed meanwhile.
export type Me = components["schemas"]["Me"] & { readonly otp_connexion_actif?: boolean };
export type Role = components["schemas"]["RoleEnum"];

/** Runtime list of roles; the type check below keeps it in sync with the generated RoleEnum. */
export const ROLES = ["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"] as const;

type Equals<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
// Compile error if ROLES and RoleEnum diverge (in either direction).
const rolesMatchSchema: Equals<(typeof ROLES)[number], Role> = true;
void rolesMatchSchema;

/** Rôle appliqué par défaut quand le serveur renvoie une valeur inconnue (moindre privilège). */
export const DEFAULT_ROLE: Role = "AUDITE";

export function toRole(value: unknown): Role {
  return ROLES.find((r) => r === value) ?? DEFAULT_ROLE;
}

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "error";

/** Next step after a password or code check (POST /api/v1/auth/login/, login/otp/, session/). */
export type Etape = "OK" | "OTP" | "CHANGER_MOT_DE_PASSE";

/** Session state answered by the /api/v1/auth/ endpoints; `me` is null at the OTP step. */
export type EtatSession = { etape: Etape; me: Me | null };
