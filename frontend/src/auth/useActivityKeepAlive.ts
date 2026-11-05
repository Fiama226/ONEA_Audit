import { useEffect } from "react";
import { fetchSession } from "./api";

/** Période de la vérification : bien en deçà des 30 minutes d'inactivité du serveur. */
export const KEEP_ALIVE_INTERVAL_MS = 10 * 60 * 1000;

/** Événements comptés comme une activité réelle de l'agent (pas le défilement ni le survol). */
const ACTIVITY_EVENTS = ["keydown", "pointerdown"] as const;

/**
 * Requête légère SANS l'en-tête d'arrière-plan : le serveur la compte comme une activité et
 * repousse le délai d'inactivité. Le résultat est ignoré : un 401 sera traité par la prochaine
 * requête de l'application.
 */
export function keepAlivePing(): Promise<void> {
  return fetchSession().then(
    () => undefined,
    () => undefined,
  );
}

/**
 * Garde la session ouverte tant que l'agent agit réellement (frappe, clic) dans un onglet
 * visible : la saisie d'un long texte ne produit aucune requête, et les interrogations
 * automatiques ne comptent volontairement pas (AUTH-08). Toutes les 10 minutes, si une
 * activité a eu lieu depuis la dernière vérification et que l'onglet est visible, une requête
 * est envoyée. Un onglet laissé sans activité expire toujours au bout de 30 minutes, et la
 * durée maximale de 8 heures reste appliquée par le serveur.
 */
export function useActivityKeepAlive(enabled: boolean, ping: () => unknown = keepAlivePing) {
  useEffect(() => {
    if (!enabled) return;
    // Activité réelle depuis la dernière requête de maintien.
    let active = false;
    const onActivity = () => {
      active = true;
    };
    for (const name of ACTIVITY_EVENTS) {
      document.addEventListener(name, onActivity, { capture: true, passive: true });
    }
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible" || !active) return;
      active = false;
      void ping();
    }, KEEP_ALIVE_INTERVAL_MS);
    return () => {
      clearInterval(timer);
      for (const name of ACTIVITY_EVENTS) {
        document.removeEventListener(name, onActivity, { capture: true });
      }
    };
  }, [enabled, ping]);
}
