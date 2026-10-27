export const ROLES = ["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"] as const;
export type Role = (typeof ROLES)[number];

/** Rôle appliqué par défaut quand le serveur renvoie une valeur inconnue (moindre privilège). */
export const DEFAULT_ROLE: Role = "AUDITE";

// Type local en attendant les types OpenAPI générés (Task 9).
export type Me = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  direction_code: string;
  fonction: string;
};

export function toRole(value: unknown): Role {
  return ROLES.find((r) => r === value) ?? DEFAULT_ROLE;
}

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "error";
