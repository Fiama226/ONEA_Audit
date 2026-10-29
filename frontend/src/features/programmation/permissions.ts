import type { Role } from "@/auth/types";

/** Création, modification, validation et suppression du programme : RAI seul. */
export function canEditAuditPlan(role: Role | null): boolean {
  return role === "RAI";
}

/** Lecture du programme annuel. */
export function canReadAuditPlan(role: Role | null): boolean {
  return role === "ADMIN" || role === "RAI" || role === "AUDITEUR" || role === "DG";
}
