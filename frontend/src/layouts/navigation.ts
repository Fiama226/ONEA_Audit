import {
  BookMarked,
  Briefcase,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";

export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Rôles autorisés ; absent = tout utilisateur authentifié. */
  roles?: readonly Role[];
};

export type NavGroup = { title?: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  { items: [{ to: "/", label: fr.nav.dashboard, icon: LayoutDashboard }] },
  {
    title: fr.nav.groupMissions,
    items: [
      { to: "/missions", label: fr.nav.missions, icon: Briefcase },
      {
        to: "/referentiel",
        label: fr.nav.referentiel,
        icon: BookMarked,
        roles: ["ADMIN", "RAI", "AUDITEUR"],
      },
    ],
  },
  {
    title: fr.nav.groupFollowUp,
    items: [
      { to: "/recommandations", label: fr.nav.recommandations, icon: ClipboardCheck },
      { to: "/documents", label: fr.nav.documents, icon: FileText },
    ],
  },
  {
    title: fr.nav.groupSettings,
    items: [
      {
        to: "/administration",
        label: fr.nav.administration,
        icon: SlidersHorizontal,
        roles: ["ADMIN"],
      },
    ],
  },
];

/** Groupes visibles pour un rôle ; un groupe sans entrée visible disparaît avec son titre. */
export function navFor(role: Role | null): NavGroup[] {
  if (role === null) return [];
  return NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.roles || i.roles.includes(role)),
  })).filter((g) => g.items.length > 0);
}

/** Libellé de chaque segment de route pour le fil d'Ariane. */
export const SEGMENT_LABELS: Record<string, string> = {
  missions: fr.nav.missions,
  referentiel: fr.nav.referentiel,
  recommandations: fr.nav.recommandations,
  documents: fr.nav.documents,
  administration: fr.nav.administration,
};
