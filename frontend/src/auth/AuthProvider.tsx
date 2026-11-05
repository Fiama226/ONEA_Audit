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
import {
  ensureCsrfToken,
  resetCsrfToken,
  setSessionChangedHandler,
  setSessionUser,
  setUnauthorizedHandler,
} from "@/api/client";
import { isApiError } from "@/api/errors";
import { fetchSession, postLogin, postLoginOtp, postLogout, postPasswordChange } from "./api";
import {
  announce,
  clearPendingLogout,
  hasPendingLogout,
  listen,
  markPendingLogout,
} from "./crossTab";
import { toRole, type AuthStatus, type Etape, type EtatSession, type Me } from "./types";
import { useActivityKeepAlive } from "./useActivityKeepAlive";
import { AuthContext, type AuthContextValue } from "./useAuth";

/** Attente maximale de la fin de session serveur lors d'un clic sur « Se déconnecter ». */
const LOGOUT_TIMEOUT_MS = 2000;
/** Attente maximale du rejeu d'une déconnexion non confirmée, au démarrage. */
const LOGOUT_REPLAY_TIMEOUT_MS = 10000;

/** Réponse qui prouve que la session de ce cookie n'existe plus : 204, 401 ou 403. */
async function endServerSession(signal?: AbortSignal): Promise<boolean> {
  try {
    await postLogout(signal);
    return true;
  } catch (e) {
    return isApiError(e) && (e.status === 401 || e.status === 403);
  }
}

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
  const [sessionChanged, setSessionChanged] = useState(false);
  const [loggedOut, setLoggedOut] = useState(false);
  const [logoutUnconfirmed, setLogoutUnconfirmed] = useState(false);
  // Lus par les gestionnaires (401, autres onglets), hors du cycle de rendu.
  const statusRef = useRef<AuthStatus>("loading");
  const meIdRef = useRef<number | undefined>(undefined);

  const changeStatus = useCallback((next: AuthStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const goAnonymous = useCallback(() => {
    resetCsrfToken();
    setSessionUser(null);
    meIdRef.current = undefined;
    setMe(undefined);
    setEtape(undefined);
    changeStatus("anonymous");
    // Les données de l'utilisateur précédent ne doivent pas rester en mémoire.
    queryClient?.clear();
  }, [changeStatus, queryClient]);

  const openSession = useCallback(
    (etat: EtatSession & { me: Me }) => {
      // Un autre agent que celui affiché : rien de l'écran précédent ne doit rester en cache.
      if (meIdRef.current !== undefined && meIdRef.current !== etat.me.id) queryClient?.clear();
      meIdRef.current = etat.me.id;
      setSessionUser(etat.me.id);
      setMe({ ...etat.me, role: toRole(etat.me.role) });
      setEtape(etat.etape);
      setErrorDetail(undefined);
      setSessionExpired(false);
      setSessionChanged(false);
      setLoggedOut(false);
      setLogoutUnconfirmed(false);
      changeStatus("authenticated");
    },
    [changeStatus, queryClient],
  );

  /** Sonde la session et applique son état (ouverte, anonyme ou panne). */
  const probe = useCallback(async () => {
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
        setSessionUser(null);
        meIdRef.current = undefined;
        setMe(undefined);
        setEtape(undefined);
        changeStatus("error");
      }
    }
  }, [changeStatus, goAnonymous, openSession]);

  const init = useCallback(async () => {
    changeStatus("loading");
    if (hasPendingLogout()) {
      // Une déconnexion n'a pas été confirmée (poste partagé, réseau lent) : la session de ce
      // cookie est fermée AVANT toute sonde, qui la prolongerait sinon.
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), LOGOUT_REPLAY_TIMEOUT_MS);
      const confirmed = await endServerSession(controller.signal);
      clearTimeout(timer);
      if (!confirmed) {
        setLoggedOut(true);
        setLogoutUnconfirmed(true);
        goAnonymous();
        return;
      }
      clearPendingLogout();
    }
    await probe();
  }, [changeStatus, goAnonymous, probe]);

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
    // Écriture refusée puis session d'un autre agent découverte avant le rejeu.
    setSessionChangedHandler(() => {
      if (statusRef.current !== "authenticated") return;
      setSessionExpired(false);
      setSessionChanged(true);
      setLoggedOut(true); // la page quittée n'est pas proposée à l'autre agent
      goAnonymous();
    });
    return () => {
      setUnauthorizedHandler(null);
      setSessionChangedHandler(null);
    };
  }, [goAnonymous]);

  /** Une session a été ouverte dans un autre onglet (cookie partagé, jeton CSRF renouvelé). */
  const followLogin = useCallback(async () => {
    resetCsrfToken();
    let etat: EtatSession;
    try {
      etat = await fetchSession();
    } catch (e) {
      if (isApiError(e) && e.status === 401 && statusRef.current === "authenticated") {
        goAnonymous();
      }
      return;
    }
    const next = etat.me && etat.etape !== "OTP" ? etat.me : undefined;
    if (statusRef.current === "authenticated" && next?.id !== meIdRef.current) {
      // Un autre agent : l'écran de l'agent affiché est quitté, rien ne lui est présenté
      // sans qu'il agisse (poste partagé). Il se reconnecte s'il le souhaite.
      setSessionExpired(false);
      setSessionChanged(true);
      setLoggedOut(true);
      goAnonymous();
      return;
    }
    if (next) openSession({ ...etat, me: next });
  }, [goAnonymous, openSession]);

  useEffect(
    () =>
      // Connexion ou déconnexion dans un autre onglet du même navigateur.
      listen((signal) => {
        if (statusRef.current === "loading") return;
        if (signal === "login") {
          void followLogin();
          return;
        }
        if (statusRef.current !== "authenticated") return;
        setSessionExpired(false);
        setLoggedOut(true);
        goAnonymous();
      }),
    [followLogin, goAnonymous],
  );

  // Saisie longue sans requête : l'activité réelle de l'agent garde la session ouverte.
  useActivityKeepAlive(status === "authenticated");

  /** Applique la réponse d'une étape de connexion (le serveur a renouvelé le jeton CSRF). */
  const applyStep = useCallback(
    async (etat: EtatSession): Promise<Etape> => {
      resetCsrfToken();
      if (etat.etape === "OTP") return "OTP";
      // La nouvelle session remplace l'ancienne côté serveur : plus rien à rejouer.
      clearPendingLogout();
      if (etat.me) openSession({ ...etat, me: etat.me });
      else await probe();
      announce("login");
      return etat.etape;
    },
    [openSession, probe],
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

  const updateMe = useCallback((changes: Partial<Me>) => {
    setMe((current) => (current ? { ...current, ...changes, role: current.role } : current));
  }, []);

  const logout = useCallback(async () => {
    // La marque reste posée tant que le serveur n'a pas confirmé la fin de session : le
    // prochain démarrage (rechargement, nouvel onglet) rejoue alors la déconnexion.
    const mark = markPendingLogout();
    // Attente bornée à 2 s : la déconnexion locale n'est jamais bloquée. La requête n'est pas
    // envoyée si le jeton CSRF arrive après le délai (le cookie peut alors être celui d'un
    // autre agent) ; une fois envoyée (keepalive), elle va à son terme et sa confirmation
    // tardive retire la marque.
    let late = false;
    const attempt = (async () => {
      try {
        await ensureCsrfToken();
      } catch {
        return false;
      }
      if (late) return false;
      const confirmed = await endServerSession();
      if (confirmed) clearPendingLogout(mark);
      return confirmed;
    })();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = new Promise<boolean>((resolve) => {
      timer = setTimeout(() => {
        late = true;
        resolve(false);
      }, LOGOUT_TIMEOUT_MS);
    });
    const confirmed = await Promise.race([attempt, deadline]);
    clearTimeout(timer);
    if (!confirmed && late) {
      void attempt.then((ok) => {
        if (ok && statusRef.current === "anonymous") setLogoutUnconfirmed(false);
      });
    }
    setSessionExpired(false);
    setSessionChanged(false);
    setLoggedOut(true);
    setLogoutUnconfirmed(!confirmed);
    goAnonymous();
    announce("logout");
  }, [goAnonymous]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      me,
      etape,
      errorDetail,
      sessionExpired,
      sessionChanged,
      loggedOut,
      logoutUnconfirmed,
      login,
      verifyOtp,
      changePassword,
      logout,
      retry: init,
      updateMe,
    }),
    [
      updateMe,
      status,
      me,
      etape,
      errorDetail,
      sessionExpired,
      sessionChanged,
      loggedOut,
      logoutUnconfirmed,
      login,
      verifyOtp,
      changePassword,
      logout,
      init,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
