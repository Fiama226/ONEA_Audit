import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { trouverCible } from "../cible";
import type { Etape } from "../etapes";

const T = fr.tutoriel;
const MARGE = 12;
const BORD = 16;
const LARGEUR = 340;

type Zone = { top: number; left: number; width: number; height: number };

const prefereMouvementReduit = () =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Place la bulle sous, au-dessus, à droite ou à gauche de la cible, selon la place disponible. */
function placer(zone: Zone | null, hauteur: number): { top: number; left: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const largeur = Math.min(LARGEUR, vw - 2 * BORD);
  const borne = (v: number, max: number) => Math.max(BORD, Math.min(v, max - BORD));
  if (!zone) {
    return { top: Math.max(BORD, (vh - hauteur) / 2), left: Math.max(BORD, (vw - largeur) / 2) };
  }
  const gauche = borne(zone.left, vw - largeur + BORD);
  const haut = borne(zone.top, vh - hauteur + BORD);
  const dessous = zone.top + zone.height + MARGE;
  if (dessous + hauteur <= vh - BORD) return { top: dessous, left: gauche };
  const dessus = zone.top - MARGE - hauteur;
  if (dessus >= BORD) return { top: dessus, left: gauche };
  const droite = zone.left + zone.width + MARGE;
  if (droite + largeur <= vw - BORD) return { top: haut, left: droite };
  const aGauche = zone.left - MARGE - largeur;
  if (aGauche >= BORD) return { top: haut, left: aGauche };
  return { top: Math.max(BORD, (vh - hauteur) / 2), left: Math.max(BORD, (vw - largeur) / 2) };
}

type Props = {
  etapes: Etape[];
  onFinish: () => void;
  /** « Passer », Échap : l'utilisateur renonce à la visite. */
  onSkip: () => void;
};

/**
 * Visite guidée : voile + surbrillance de l'élément réel + bulle de dialogue modale.
 * Clavier : Tab piégé dans la bulle, flèches gauche/droite, Échap pour passer.
 * Aucune animation : le mouvement réduit est respecté d'office.
 */
export function TourPopover({ etapes, onFinish, onSkip }: Props) {
  const [index, setIndex] = useState(0);
  const [zone, setZone] = useState<Zone | null>(null);
  const [pos, setPos] = useState({ top: BORD, left: BORD });
  const bulle = useRef<HTMLDivElement>(null);
  const titreId = useId();
  const texteId = useId();
  const etape = etapes[index] ?? etapes[0]!;
  const dernier = index === etapes.length - 1;

  const suivant = () => (dernier ? onFinish() : setIndex((i) => i + 1));
  const precedent = () => setIndex((i) => Math.max(0, i - 1));
  const actions = useRef({ suivant, precedent, onSkip });
  useEffect(() => {
    actions.current = { suivant, precedent, onSkip };
  });

  // Focus : à l'ouverture sur la bulle (nom + description annoncés), rendu à la fermeture.
  useEffect(() => {
    const avant = document.activeElement;
    return () => {
      if (avant instanceof HTMLElement && avant.isConnected) avant.focus();
    };
  }, []);
  useEffect(() => {
    bulle.current?.focus();
  }, [index]);

  // Mesure de la cible et suivi du défilement / redimensionnement.
  useEffect(() => {
    const cible = trouverCible(etape.cibles);
    if (!cible) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setZone(null);
      return;
    }
    cible.scrollIntoView?.({
      block: "nearest",
      behavior: prefereMouvementReduit() ? "auto" : "smooth",
    });
    const mesurer = () => {
      const r = cible.getBoundingClientRect();
      setZone({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    mesurer();
    window.addEventListener("resize", mesurer);
    window.addEventListener("scroll", mesurer, true);
    return () => {
      window.removeEventListener("resize", mesurer);
      window.removeEventListener("scroll", mesurer, true);
    };
  }, [etape]);

  useLayoutEffect(() => {
     
    setPos(placer(zone, bulle.current?.offsetHeight ?? 0));
  }, [zone, index]);

  // Clavier global : Échap, flèches, et focus maintenu dans la bulle.
  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        actions.current.onSkip();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        actions.current.suivant();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        actions.current.precedent();
      } else if (e.key === "Tab" && bulle.current) {
        const focalisables = [
          ...bulle.current.querySelectorAll<HTMLElement>("button:not([disabled])"),
        ];
        const premier = focalisables[0];
        const dernierEl = focalisables[focalisables.length - 1];
        const actif = document.activeElement;
        if (e.shiftKey && (actif === premier || actif === bulle.current)) {
          e.preventDefault();
          dernierEl?.focus();
        } else if (!e.shiftKey && actif === dernierEl) {
          e.preventDefault();
          premier?.focus();
        } else if (!bulle.current.contains(actif)) {
          e.preventDefault();
          premier?.focus();
        }
      }
    };
    const surFocus = (e: FocusEvent) => {
      if (bulle.current && e.target instanceof Node && !bulle.current.contains(e.target)) {
        bulle.current.focus();
      }
    };
    document.addEventListener("keydown", surTouche);
    document.addEventListener("focusin", surFocus);
    return () => {
      document.removeEventListener("keydown", surTouche);
      document.removeEventListener("focusin", surFocus);
    };
  }, []);

  const texte = T.steps[etape.id];
  const progres = { n: String(index + 1), total: String(etapes.length) };
  const remplir = (m: string) => m.replace("{n}", progres.n).replace("{total}", progres.total);

  return createPortal(
    <div data-testid="tutoriel-visite">
      {/* Voile : capte les clics pour que la page reste inerte pendant la visite. */}
      <div aria-hidden className={`fixed inset-0 z-[70] ${zone ? "" : "bg-overlay"}`} />
      {zone && (
        <div
          aria-hidden
          data-testid="tutoriel-surbrillance"
          className="pointer-events-none fixed z-[70] rounded-md ring-2 ring-brand-accent"
          style={{
            top: zone.top - 4,
            left: zone.left - 4,
            width: zone.width + 8,
            height: zone.height + 8,
            boxShadow: "0 0 0 9999px var(--overlay)",
          }}
        />
      )}
      <div
        ref={bulle}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titreId}
        aria-describedby={texteId}
        tabIndex={-1}
        className="fixed z-[71] rounded-lg border border-border bg-surface p-4 text-foreground shadow-floating outline-none focus-visible:ring-2 focus-visible:ring-ring"
        style={{
          top: pos.top,
          left: pos.left,
          width: Math.min(LARGEUR, window.innerWidth - 2 * BORD),
        }}
      >
        <p className="text-xs font-medium text-text-muted">
          <span aria-hidden>{remplir(T.progress)}</span>
          <span className="sr-only">{remplir(T.progressSr)}</span>
        </p>
        <h2 id={titreId} className="mt-1 text-base font-semibold">
          {texte.title}
        </h2>
        <p id={texteId} className="mt-1 text-sm">
          {texte.body}
        </p>
        <div className="mt-4 flex items-center justify-between gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            {T.skip}
          </Button>
          <div className="flex gap-2">
            {index > 0 && (
              <Button type="button" variant="outline" size="sm" onClick={precedent}>
                {T.previous}
              </Button>
            )}
            <Button type="button" size="sm" onClick={suivant}>
              {dernier ? T.finish : T.next}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
