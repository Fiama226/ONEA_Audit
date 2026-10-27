import { UserManager, WebStorageStateStore } from "oidc-client-ts";

/** Sous-ensemble de l'utilisateur OIDC utilisé par l'application. */
export type OidcUser = {
  access_token: string;
  expired?: boolean;
  state?: unknown;
};

/** Sous-ensemble de UserManager injecté dans AuthProvider (permet de le simuler en test). */
export interface OidcClient {
  getUser(): Promise<OidcUser | null>;
  signinRedirect(args?: { state?: unknown }): Promise<void>;
  signinRedirectCallback(): Promise<OidcUser>;
  signoutRedirect(): Promise<void>;
  removeUser(): Promise<void>;
  events: {
    addUserLoaded(cb: (user: OidcUser) => void): void;
    removeUserLoaded(cb: (user: OidcUser) => void): void;
  };
}

export function createUserManager(): OidcClient {
  const env = import.meta.env;
  const authority =
    (env.VITE_OIDC_AUTHORITY as string | undefined) ?? "http://localhost:8080/realms/onea";
  const clientId = (env.VITE_OIDC_CLIENT_ID as string | undefined) ?? "onea-frontend";
  return new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: `${window.location.origin}/callback`,
    post_logout_redirect_uri: window.location.origin,
    scope: "openid profile email",
    response_type: "code", // PKCE S256 par défaut
    automaticSilentRenew: true,
    // sessionStorage : le jeton ne survit pas à la fermeture de l'onglet et n'est pas dans localStorage.
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });
}
