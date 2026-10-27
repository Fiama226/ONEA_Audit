import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "onea.sidebar";
const WIDE_QUERY = "(min-width: 1280px)";

type Choice = "collapsed" | "expanded";

function readStored(): Choice | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "collapsed" || stored === "expanded" ? stored : null;
  } catch {
    return null; // stockage indisponible (navigation privée, accès refusé)
  }
}

function matchesWide(): boolean | null {
  return typeof window.matchMedia === "function" ? window.matchMedia(WIDE_QUERY).matches : null;
}

/**
 * État replié de la barre latérale. Sans choix de l'utilisateur, il suit la largeur d'écran
 * (repliée entre 1024 et 1279 px) ; dès qu'il bascule, son choix prime et est mémorisé dans
 * localStorage (sans jamais échouer).
 */
export function useSidebarCollapsed(): [boolean, () => void] {
  const [choice, setChoice] = useState<Choice | null>(readStored);
  const [wide, setWide] = useState<boolean | null>(matchesWide);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(WIDE_QUERY);
    const onChange = (e: MediaQueryListEvent) => setWide(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const collapsed = choice ? choice === "collapsed" : wide === false;

  const toggle = useCallback(() => {
    const next: Choice = collapsed ? "expanded" : "collapsed";
    setChoice(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // le choix n'est alors pas mémorisé
    }
  }, [collapsed]);

  return [collapsed, toggle];
}
