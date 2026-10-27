import { useCallback } from "react";
import { DEFAULT_ROLE, type Role } from "./types";
import { useAuth } from "./useAuth";

export function useRole(): { role: Role; is: (...roles: Role[]) => boolean } {
  const { me } = useAuth();
  const role = me?.role ?? DEFAULT_ROLE;
  const is = useCallback((...roles: Role[]) => roles.includes(role), [role]);
  return { role, is };
}
