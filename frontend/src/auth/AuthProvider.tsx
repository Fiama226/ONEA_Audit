import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { apiFetch, setTokenProvider, setUnauthorizedHandler } from "@/api/client";
import { isApiError } from "@/api/errors";
import { createUserManager, type OidcClient, type OidcUser } from "./oidc";
import { safeReturnPath } from "./safePath";
import { toRole, type AuthStatus, type Me } from "./types";
import { AuthContext, type AuthContextValue } from "./useAuth";

const END_SESSION_TIMEOUT_MS = 2000;

type Props = { children: ReactNode; userManager?: OidcClient };

function returnToOf(user: OidcUser): string {
  const state = user.state;
  if (typeof state === "object" && state !== null && "returnTo" in state) {
    return safeReturnPath((state as { returnTo: unknown }).returnTo);
  }
  return "/";
}

export function AuthProvider({ children, userManager }: Props) {
  const [oidc] = useState<OidcClient>(() => userManager ?? createUserManager());
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | undefined>(undefined);
  const [errorDetail, setErrorDetail] = useState<string | undefined>(undefined);
  const [sessionExpired, setSessionExpired] = useState(false);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    setTokenProvider(() => tokenRef.current);
  }, []);

  const goAnonymous = useCallback(async () => {
    tokenRef.current = null;
    setMe(undefined);
    setStatus("anonymous");
    try {
      await oidc.removeUser();
    } catch {
      // le stockage local est déjà considéré comme vide
    }
  }, [oidc]);

  useEffect(() => {
    // 401 en cours d'utilisation (session terminée ailleurs, jeton révoqué) : retour à la connexion.
    setUnauthorizedHandler(() => {
      if (tokenRef.current === null) return;
      setSessionExpired(true);
      void goAnonymous();
    });
    return () => setUnauthorizedHandler(null);
  }, [goAnonymous]);

  useEffect(() => {
    const onLoaded = (user: OidcUser) => {
      tokenRef.current = user.access_token;
    };
    const onExpired = () => {
      setSessionExpired(true);
      void goAnonymous();
    };
    oidc.events.addUserLoaded(onLoaded);
    oidc.events.addAccessTokenExpired(onExpired);
    oidc.events.addSilentRenewError(onExpired);
    return () => {
      oidc.events.removeUserLoaded(onLoaded);
      oidc.events.removeAccessTokenExpired(onExpired);
      oidc.events.removeSilentRenewError(onExpired);
    };
  }, [oidc, goAnonymous]);

  /** Charge /me avec le jeton courant. */
  const loadMe = useCallback(async () => {
    try {
      const data = await apiFetch<Me>("/api/v1/me/");
      setErrorDetail(undefined);
      setMe({ ...data, role: toRole(data.role) });
      setStatus("authenticated");
    } catch (e) {
      if (isApiError(e) && e.status === 401) {
        await goAnonymous();
      } else {
        // 403 : compte désactivé. Ce n'est pas une session expirée, donc pas de retour vers la connexion.
        setErrorDetail(isApiError(e) && e.status === 403 ? e.detail : undefined);
        setMe(undefined);
        setStatus("error");
      }
    }
  }, [goAnonymous]);

  const init = useCallback(async () => {
    setStatus("loading");
    try {
      const user = await oidc.getUser();
      if (!user || user.expired) {
        tokenRef.current = null;
        setStatus("anonymous");
        return;
      }
      tokenRef.current = user.access_token;
    } catch {
      setStatus("error");
      return;
    }
    await loadMe();
  }, [oidc, loadMe]);

  useEffect(() => {
    // Initialisation asynchrone au montage ; les setState surviennent après await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void init();
  }, [init]);

  const login = useCallback(
    async (returnTo?: string) => {
      setSessionExpired(false);
      try {
        await oidc.signinRedirect({ state: { returnTo: safeReturnPath(returnTo) } });
      } catch {
        setStatus("error");
      }
    },
    [oidc],
  );

  const logout = useCallback(async () => {
    // Fin de session côté serveur (purge du cache userinfo), au plus 2 s ; un échec n'empêche
    // jamais la déconnexion Keycloak.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), END_SESSION_TIMEOUT_MS);
    try {
      await apiFetch<void>("/api/v1/session/fin/", { method: "POST", signal: controller.signal });
    } catch {
      // ignoré : voir ci-dessus
    } finally {
      clearTimeout(timer);
    }
    tokenRef.current = null;
    setMe(undefined);
    setStatus("anonymous");
    try {
      await oidc.signoutRedirect();
    } catch {
      await goAnonymous();
    }
  }, [oidc, goAnonymous]);

  const completeLogin = useCallback(async () => {
    let user: OidcUser;
    try {
      user = await oidc.signinRedirectCallback();
    } catch {
      setStatus("error");
      return null;
    }
    tokenRef.current = user.access_token;
    await loadMe();
    return returnToOf(user);
  }, [oidc, loadMe]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, me, errorDetail, sessionExpired, login, logout, retry: init, completeLogin }),
    [status, me, errorDetail, sessionExpired, login, logout, init, completeLogin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
