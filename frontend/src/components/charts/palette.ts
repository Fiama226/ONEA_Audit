import { AlertTriangle, CheckCircle2, Circle, type LucideIcon } from "lucide-react";
import { fr } from "@/i18n/fr";

export type SerieStatut = "done" | "open" | "late";

export interface SerieInfo {
  label: string;
  icon: LucideIcon;
  /** Classe Tailwind de remplissage (token `--chart-*`). */
  fill: string;
  /** Classe de texture ajoutée (jamais la couleur seule). */
  texture?: string;
}

/** Séries de statut des actions : couleur, icône et libellé (clôturées, ouvertes, en retard). */
export const SERIES_STATUT: Record<SerieStatut, SerieInfo> = {
  done: { label: fr.charts.done, icon: CheckCircle2, fill: "bg-chart-done chart-seg" },
  open: { label: fr.charts.open, icon: Circle, fill: "bg-chart-open chart-seg" },
  late: {
    label: fr.charts.late,
    icon: AlertTriangle,
    fill: "bg-chart-late chart-seg chart-seg-late",
    texture: "chart-late-texture",
  },
};

export const SERIE_ORDER: SerieStatut[] = ["done", "open", "late"];

function luminance(hex: string): number {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) throw new Error(`Couleur hexadécimale invalide : ${hex}`);
  const n = parseInt(m[1] ?? "", 16);
  const lin = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const [r = 0, g = 0, b = 0] = lin;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Rapport de contraste WCAG 2.x entre deux couleurs `#rrggbb`. */
export function contrastRatio(hexA: string, hexB: string): number {
  const a = luminance(hexA);
  const b = luminance(hexB);
  const [hi, lo] = a >= b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

export function fmtInt(n: number): string {
  return n.toLocaleString("fr-FR");
}
