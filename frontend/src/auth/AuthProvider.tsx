import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { apiFetch, setTokenProvider } from "@/api/client";
import { isApiError } from "@/api/errors";
import { createUserManager, type OidcClient, type OidcUser } from "./oidc";
import { toRole, type AuthStatus, type Me } from "./types";
import { AuthContext, type AuthContextValue } from "./useAuth";

type Props = { children: ReactNode; userManager?: OidcClient };

function returnToOf(user: OidcUser): string {
  const state = user.state;
  if (typeof state === "object" && state !== null && "returnTo" in state) {
    const value = (state as { returnTo: unknown }).returnTo;
    if (typeof value === "string" && value.startsWith("/") && !value.startsWith("//")) return value;
  }
  return "/";
}

export function AuthProvider({ children, userManager }: Props) {
  const [oidc] = useState<OidcClient>(() => userManager ?? createUserManager());
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | undefined>(undefined);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    setTokenProvider(() => tokenRef.current);
  }, []);

  useEffect(() => {
    const onLoaded = (user: OidcUser) => {
      tokenRef.current = user.access_token;
    };
    oidc.events.addUserLoaded(onLoaded);
    return () => oidc.events.removeUserLoaded(onLoaded);
  }, [oidc]);

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

  /** Charge /me avec le jeton courant. */
  const loadMe = useCallback(async () => {
    try {
      const data = await apiFetch<Me>("/api/v1/me/");
      setMe({ ...data, role: toRole(data.role) });
      setStatus("authenticated");
    } catch (e) {
      if (isApiError(e) && e.status === 401) {
        await goAnonymous();
      } else {
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
      try {
        await oidc.signinRedirect({ state: { returnTo: returnTo ?? "/" } });
      } catch {
        setStatus("error");
      }
    },
    [oidc],
  );

  const logout = useCallback(async () => {
    tokenRef.current = null;
    setMe(undefined);
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
    () => ({ status, me, login, logout, retry: init, completeLogin }),
    [status, me, login, logout, init, completeLogin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
