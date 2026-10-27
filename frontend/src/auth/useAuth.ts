import { createContext, useContext } from "react";
import type { AuthStatus, Me } from "./types";

export type AuthContextValue = {
  status: AuthStatus;
  me?: Me;
  /** Vrai quand la session a expiré (jeton expiré ou renouvellement échoué). */
  sessionExpired: boolean;
  /** Lance la connexion ; `returnTo` est restitué après le retour de Keycloak. */
  login(returnTo?: string): Promise<void>;
  logout(): Promise<void>;
  /** Relance l'initialisation (bouton « Réessayer »). */
  retry(): Promise<void>;
  /** Termine la connexion sur /callback ; renvoie le chemin demandé à l'origine, ou null en cas d'échec. */
  completeLogin(): Promise<string | null>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans un AuthProvider");
  return ctx;
}
