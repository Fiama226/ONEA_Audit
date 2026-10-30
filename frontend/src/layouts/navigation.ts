import {
  BookMarked,
  Briefcase,
  CalendarRange,
  ClipboardCheck,
  FileCog,
  FileText,
  LayoutDashboard,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";

/**
 * Source unique des restrictions par route : la barre latérale et les gardes de routes
 * (routes.tsx) lisent cette table. Absent = tout utilisateur authentifié.
 */
const ROUTE_ROLES: Readonly<Record<string, readonly Role[]>> = {
  "/programme-annuel": ["ADMIN", "RAI", "AUDITEUR", "DG"],
  "/missions": ["RAI", "AUDITEUR", "AUDITE"],
  "/referentiel": ["ADMIN", "RAI", "AUDITEUR", "DG"],
  // ADMIN et DG n'ont pas accès aux documents de mission (l'ADMIN gère les gabarits en /administration).
  "/documents": ["RAI", "AUDITEUR", "AUDITE"],
  // Gabarits et numérotation : lecture ADMIN et RAI ; les écritures restent ADMIN (le serveur répond 403).
  "/administration/documents": ["ADMIN", "RAI"],
  "/administration/signatures": ["ADMIN", "RAI"],
  "/administration": ["ADMIN"],
};

export function rolesFor(path: string): readonly Role[] | undefined {
  return ROUTE_ROLES[path];
}

export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Préfixe de chemin pour lequel l'entrée n'est pas marquée active (entrée voisine plus précise). */
  exclude?: string;
};

export type NavGroup = { title?: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  { items: [{ to: "/", label: fr.nav.dashboard, icon: LayoutDashboard }] },
  {
    title: fr.nav.groupMissions,
    items: [
      { to: "/programme-annuel", label: fr.nav.programmeAnnuel, icon: CalendarRange },
      { to: "/missions", label: fr.nav.missions, icon: Briefcase },
      {
        to: "/referentiel",
        label: fr.nav.referentiel,
        icon: BookMarked,
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
        exclude: "/administration/documents",
      },
      {
        to: "/administration/documents",
        label: fr.nav.documentTemplates,
        icon: FileCog,
      },
    ],
  },
];

/** Groupes visibles pour un rôle ; un groupe sans entrée visible disparaît avec son titre. */
export function navFor(role: Role | null): NavGroup[] {
  if (role === null) return [];
  return NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => rolesFor(i.to)?.includes(role) ?? true),
  })).filter((g) => g.items.length > 0);
}

/** Libellé de chaque segment de route pour le fil d'Ariane. */
export const SEGMENT_LABELS: Record<string, string> = {
  missions: fr.nav.missions,
  "programme-annuel": fr.nav.programmeAnnuel,
  "nouvelle-ligne": fr.programmation.newLine,
  lignes: "Missions prévues",
  referentiel: fr.nav.referentiel,
  recommandations: fr.nav.recommandations,
  documents: fr.nav.documents,
  gabarits: fr.documents.tabTemplates,
  numerotation: fr.documents.tabNumbering,
  signatures: fr.signatureAdmin.title,
  administration: fr.nav.administration,
  utilisateurs: fr.utilisateurs.title,
  cartographies: fr.referentiel.tabCartographies,
  risques: fr.referentiel.risques,
  processus: fr.referentiel.tabProcessus,
  directions: fr.referentiel.tabDirections,
  "objets-auditables": fr.referentiel.tabObjets,
  nouveau: fr.referentiel.newItem,
  comparer: fr.referentiel.compare,
  nouvelle: fr.missions.newMission,
  modifier: fr.common.edit,
  etapes: fr.missions.tabSteps,
  equipe: fr.missions.tabTeam,
  reunions: fr.missions.tabMeetings,
  entretiens: fr.missions.tabInterviews,
  suivi: fr.missions.tabTracking,
  "referentiel-audit": fr.missions.tabAuditFramework,
  fiches: fr.missions.tabFiches,
  constats: fr.missions.tabConstats,
};
