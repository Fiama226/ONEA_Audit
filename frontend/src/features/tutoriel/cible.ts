/** Vrai si l'élément et ses ancêtres sont affichés (ni `display: none`, ni `visibility: hidden`, ni `hidden`) ; `aria-hidden` est ignoré : Radix le pose sur la page pendant la bienvenue. */
function estAffiche(el: Element): boolean {
  for (let n: Element | null = el; n; n = n.parentElement) {
    const style = getComputedStyle(n);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (n.hasAttribute("hidden")) return false;
  }
  return true;
}

/** Premier élément affiché portant l'un des `data-tour` donnés (dans l'ordre), sinon null. */
export function trouverCible(cibles: readonly string[]): HTMLElement | null {
  for (const cible of cibles) {
    const candidats = document.querySelectorAll<HTMLElement>(`[data-tour="${cible}"]`);
    for (const el of candidats) if (estAffiche(el)) return el;
  }
  return null;
}
