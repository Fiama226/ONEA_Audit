import { useCallback, useState } from "react";

export const SIDEBAR_STORAGE_KEY = "onea.sidebar";

function readInitial(): boolean {
  try {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (stored === "collapsed") return true;
    if (stored === "expanded") return false;
  } catch {
    // stockage indisponible (navigation privée, accès refusé) : valeur par défaut
  }
  // Sans choix mémorisé : repliée entre 1024 et 1279 px, dépliée au-delà.
  if (typeof window.matchMedia === "function") {
    return !window.matchMedia("(min-width: 1280px)").matches;
  }
  return false;
}

/** État replié de la barre latérale, mémorisé dans localStorage (sans jamais échouer). */
export function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(readInitial);
  const toggle = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "collapsed" : "expanded");
      } catch {
        // le choix n'est alors pas mémorisé
      }
      return next;
    });
  }, []);
  return [collapsed, toggle];
}
