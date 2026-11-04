import { QueryClientContext } from "@tanstack/react-query";
import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { resetCsrfToken, setUnauthorizedHandler } from "@/api/client";
import { isApiError } from "@/api/errors";
import { fetchSession, postLogin, postLoginOtp, postLogout, postPasswordChange } from "./api";
import { toRole, type AuthStatus, type Etape, type EtatSession, type Me } from "./types";
import { AuthContext, type AuthContextValue } from "./useAuth";

const LOGOUT_TIMEOUT_MS = 2000;

/**
 * Session de l'application : cookie de session posé par l'API (/api/v1/auth/), sondé au
 * démarrage par GET /api/v1/auth/session/ (401 : anonyme).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  // Facultatif : certains tests montent le fournisseur sans client de requêtes.
  const queryClient = useContext(QueryClientContext);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | undefined>(undefined);
  const [etape, setEtape] = useState<Etape | undefined>(undefined);
  const [errorDetail, setErrorDetail] = useState<string | undefined>(undefined);
  const [sessionExpired, setSessionExpired] = useState(false);
  // Lu par le gestionnaire de 401, hors du cycle de rendu.
  const statusRef = useRef<AuthStatus>("loading");

  const changeStatus = useCallback((next: AuthStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const goAnonymous = useCallback(() => {
    resetCsrfToken();
    setMe(undefined);
    setEtape(undefined);
    changeStatus("anonymous");
    // Les données de l'utilisateur précédent ne doivent pas rester en mémoire.
    queryClient?.clear();
  }, [changeStatus, queryClient]);

  const openSession = useCallback(
    (etat: EtatSession & { me: Me }) => {
      setMe({ ...etat.me, role: toRole(etat.me.role) });
      setEtape(etat.etape);
      setErrorDetail(undefined);
      setSessionExpired(false);
      changeStatus("authenticated");
    },
    [changeStatus],
  );

  const init = useCallback(async () => {
    changeStatus("loading");
    try {
      const etat = await fetchSession();
      if (etat.me && etat.etape !== "OTP") openSession({ ...etat, me: etat.me });
      else goAnonymous();
    } catch (e) {
      if (isApiError(e) && e.status === 401) {
        goAnonymous();
      } else {
        // 403 : refus explicite du serveur, affiché tel quel ; sinon panne technique.
        setErrorDetail(isApiError(e) && e.status === 403 ? e.detail : undefined);
        setMe(undefined);
        setEtape(undefined);
        changeStatus("error");
      }
    }
  }, [changeStatus, goAnonymous, openSession]);

  useEffect(() => {
    // Sonde asynchrone au montage ; les setState surviennent après await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void init();
  }, [init]);

  useEffect(() => {
    // 401 en cours d'utilisation (inactivité, durée maximale, session fermée ailleurs).
    setUnauthorizedHandler(() => {
      if (statusRef.current !== "authenticated") return;
      setSessionExpired(true);
      goAnonymous();
    });
    return () => setUnauthorizedHandler(null);
  }, [goAnonymous]);

  /** Applique la réponse d'une étape de connexion (le serveur a renouvelé le jeton CSRF). */
  const applyStep = useCallback(
    async (etat: EtatSession): Promise<Etape> => {
      resetCsrfToken();
      if (etat.etape === "OTP") return "OTP";
      if (etat.me) openSession({ ...etat, me: etat.me });
      else await init();
      return etat.etape;
    },
    [init, openSession],
  );

  const login = useCallback(
    async (identifiant: string, motDePasse: string) =>
      applyStep(await postLogin(identifiant, motDePasse)),
    [applyStep],
  );

  const verifyOtp = useCallback(
    async (code: string) => applyStep(await postLoginOtp(code)),
    [applyStep],
  );

  const changePassword = useCallback(
    async (ancien: string, nouveau: string) => {
      await applyStep(await postPasswordChange(ancien, nouveau));
    },
    [applyStep],
  );

  const logout = useCallback(async () => {
    // Fin de session côté serveur, au plus 2 s ; un échec n'empêche jamais la déconnexion locale.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), LOGOUT_TIMEOUT_MS);
    try {
      await postLogout(controller.signal);
    } catch {
      // ignoré : voir ci-dessus
    } finally {
      clearTimeout(timer);
    }
    setSessionExpired(false);
    goAnonymous();
  }, [goAnonymous]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      me,
      etape,
      errorDetail,
      sessionExpired,
      login,
      verifyOtp,
      changePassword,
      logout,
      retry: init,
    }),
    [
      status,
      me,
      etape,
      errorDetail,
      sessionExpired,
      login,
      verifyOtp,
      changePassword,
      logout,
      init,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
