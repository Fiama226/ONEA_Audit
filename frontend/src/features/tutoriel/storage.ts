import { TUTORIEL_VERSION } from "./etapes";

/** Mémoire de session : évite de reproposer la visite en boucle si l'enregistrement échoue. */
const cle = (userId: number) => `onea.tutoriel.v${TUTORIEL_VERSION}.${userId}`;

export function dejaTraiteEnSession(userId: number): boolean {
  try {
    return sessionStorage.getItem(cle(userId)) === "1";
  } catch {
    return false;
  }
}

export function memoriserEnSession(userId: number, traite: boolean): void {
  try {
    if (traite) sessionStorage.setItem(cle(userId), "1");
    else sessionStorage.removeItem(cle(userId));
  } catch {
    /* stockage indisponible : sans effet, l'état serveur fait foi */
  }
}
