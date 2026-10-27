import { useCallback } from "react";
import type { Role } from "./types";
import { useAuth } from "./useAuth";

/** `role` est null tant qu'aucun utilisateur n'est chargé : aucun droit n'est alors accordé. */
export function useRole(): { role: Role | null; is: (...roles: Role[]) => boolean } {
  const { me } = useAuth();
  const role = me?.role ?? null;
  const is = useCallback((...roles: Role[]) => role !== null && roles.includes(role), [role]);
  return { role, is };
}
