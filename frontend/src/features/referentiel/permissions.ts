import type { Role } from "@/auth/types";

/** Directions, processus et objets auditables : écriture RAI et ADMIN. */
export function canEditStructure(role: Role | null): boolean {
  return role === "RAI" || role === "ADMIN";
}

/** Cartographies et risques : écriture réservée au RAI. */
export function canEditCartographie(role: Role | null): boolean {
  return role === "RAI";
}
