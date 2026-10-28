import type { Role } from "@/auth/types";

/** Directions et processus : écriture RAI et ADMIN. */
export function canEditStructure(role: Role | null): boolean {
  return role === "RAI" || role === "ADMIN";
}

/** Cartographies et risques : écriture réservée au RAI. */
export function canEditCartographie(role: Role | null): boolean {
  return role === "RAI";
}

/** Objets auditables : écriture réservée au RAI (comme le backend). */
export function canEditAuditableObjects(role: Role | null): boolean {
  return canEditCartographie(role);
}
