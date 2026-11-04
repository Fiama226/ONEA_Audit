import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { envoyerAction, type TutorielAction } from "./api";
import { trouverCible } from "./cible";
import { TutorielContext } from "./context";
import { etapesPour, TUTORIEL_VERSION, type Etape } from "./etapes";
import { dejaTraiteEnSession, memoriserEnSession } from "./storage";
import { WelcomeDialog } from "./components/WelcomeDialog";

type Phase = "repos" | "accueil" | "visite";

/** La bulle de visite n'est utile qu'une fois la visite lancée : hors du JS d'entrée. */
const TourPopover = lazy(async () => ({
  default: (await import("./components/TourPopover")).TourPopover,
}));

const PAGES_PUBLIQUES = [
  "/connexion",
  "/mot-de-passe-oublie",
  "/mot-de-passe/reinitialiser",
  "/mot-de-passe/changer",
  "/erreur",
];

/**
 * Propose la visite guidée au premier passage (version courante non vue) et expose
 * `relancer()` (page « Mon compte », menu utilisateur). Ne bloque jamais l'utilisateur :
 * toute erreur d'enregistrement est ignorée, et la session mémorise le choix pour ne pas
 * reproposer la visite en boucle.
 */
export function TutorielProvider({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const { pathname } = useLocation();
  const [phase, setPhase] = useState<Phase>("repos");
  const [etapes, setEtapes] = useState<Etape[]>([]);
  const propose = useRef(false);

  const userId = me?.id;
  const role = me?.role;
  const etat = me?.tutoriel;
  const vue = etat ? etat.version_vue !== null && etat.version_vue >= TUTORIEL_VERSION : true;
  const publique = PAGES_PUBLIQUES.includes(pathname);

  useEffect(() => {
    if (propose.current || userId === undefined || !etat || vue || publique) return;
    if (dejaTraiteEnSession(userId)) return;
    propose.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPhase("accueil");
  }, [userId, etat, vue, publique]);

  const enregistrer = useCallback(
    async (action: TutorielAction) => {
      if (userId === undefined) return;
      // Mémorisé avant l'appel : un échec réseau ne doit jamais faire rebondir la visite.
      memoriserEnSession(userId, action !== "reinitialiser");
      try {
        await envoyerAction(action, TUTORIEL_VERSION);
      } catch {
        /* silencieux : l'utilisateur n'est jamais bloqué par le suivi du tutoriel */
      }
    },
    [userId],
  );

  const demarrer = useCallback(() => {
    if (!role) return;
    const retenues = etapesPour(role).filter((e) => trouverCible(e.cibles));
    if (retenues.length === 0) {
      setPhase("repos");
      void enregistrer("terminer");
      return;
    }
    setEtapes(retenues);
    setPhase("visite");
  }, [role, enregistrer]);

  const terminer = useCallback(() => {
    setPhase("repos");
    void enregistrer("terminer");
  }, [enregistrer]);

  const ignorer = useCallback(() => {
    setPhase("repos");
    void enregistrer("ignorer");
  }, [enregistrer]);

  const relancer = useCallback(() => {
    void enregistrer("reinitialiser");
    demarrer();
  }, [enregistrer, demarrer]);

  const valeur = useMemo(() => ({ relancer }), [relancer]);

  return (
    <TutorielContext.Provider value={valeur}>
      {children}
      {phase === "accueil" && role && (
        <WelcomeDialog role={role} onStart={demarrer} onLater={ignorer} />
      )}
      {phase === "visite" && (
        <Suspense fallback={null}>
          <TourPopover etapes={etapes} onFinish={terminer} onSkip={ignorer} />
        </Suspense>
      )}
    </TutorielContext.Provider>
  );
}
