import type { DroitsGestionComptes } from "./types";
import { useAuth } from "./useAuth";

const NONE: DroitsGestionComptes = {
  creer: false,
  reinitialiser: false,
  roles: false,
  desactiver: false,
};

export type AccountRights = {
  /** ADMIN role: manages delegations, imports, and assigns the ADMIN role. */
  isAdmin: boolean;
  /** Effective rights (all of them for an ADMIN, delegated ones otherwise). */
  rights: DroitsGestionComptes;
  /** At least one right: the account administration is reachable. */
  canManage: boolean;
};

/**
 * Account-management rights of the current user, read from `me.gestion_comptes`. They only
 * drive what is shown: the server checks every action again on the target account.
 */
export function useAccountRights(): AccountRights {
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const rights = me?.gestion_comptes ?? NONE;
  return { isAdmin, rights, canManage: isAdmin || Object.values(rights).some(Boolean) };
}
