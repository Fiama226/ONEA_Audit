import { createContext, useContext } from "react";
import type { AuthStatus, Etape, Me } from "./types";

export type AuthContextValue = {
  status: AuthStatus;
  me?: Me;
  /** Étape de la session ouverte : "CHANGER_MOT_DE_PASSE" impose le changement avant tout. */
  etape?: Etape;
  /** Message du serveur (403 sur la sonde de session) ; vide pour une indisponibilité technique. */
  errorDetail?: string;
  /** Vrai quand la session a expiré en cours d'utilisation (401 de l'API). */
  sessionExpired: boolean;
  /** Vrai après une déconnexion volontaire : la page quittée n'est pas proposée au suivant. */
  loggedOut: boolean;
  /**
   * Vérifie identifiant et mot de passe. Renvoie "OTP" si un code par courriel est attendu
   * (session pas encore ouverte), sinon l'étape de la session ouverte. Rejette en ApiError.
   */
  login(identifiant: string, motDePasse: string): Promise<Etape>;
  /** Vérifie le code reçu par courriel et ouvre la session. Rejette en ApiError. */
  verifyOtp(code: string): Promise<Etape>;
  /** Change le mot de passe de l'utilisateur connecté. Rejette en ApiError. */
  changePassword(ancien: string, nouveau: string): Promise<void>;
  logout(): Promise<void>;
  /** Relance la sonde de session (bouton « Réessayer »). */
  retry(): Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans un AuthProvider");
  return ctx;
}
