import { ChevronRight } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { fr } from "@/i18n/fr";
import { SEGMENT_LABELS } from "./navigation";

type Crumb = { to: string; label: string; linkable: boolean };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Libellé d'un segment ; un identifiant prend le nom de l'objet désigné par le segment précédent. */
function labelFor(segment: string, previous: string | undefined): string {
  if (UUID.test(segment)) {
    if (previous === "cartographies") return fr.refCartographie.crumbMap;
    if (previous === "risques") return fr.refCartographie.crumbRisk;
    return fr.referentiel.detail;
  }
  if (previous === "etapes" && /^\d+$/.test(segment)) {
    return `${fr.missions.stepPrefix} ${toRoman(Number(segment))}`;
  }
  if (segment === "nouveau" && previous === "risques") return fr.refCartographie.crumbNewRisk;
  return SEGMENT_LABELS[segment] ?? segment;
}

const ROMAN: [number, string][] = [
  [10, "X"],
  [9, "IX"],
  [5, "V"],
  [4, "IV"],
  [1, "I"],
];

function toRoman(n: number): string {
  let out = "";
  let rest = n;
  for (const [value, symbol] of ROMAN) {
    while (rest >= value) {
      out += symbol;
      rest -= value;
    }
  }
  return out || String(n);
}

function crumbsFor(pathname: string): Crumb[] {
  const root: Crumb = { to: "/", label: fr.nav.dashboard, linkable: true };
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [root];
  const crumbs: Crumb[] = [root];
  segments.forEach((segment, i) => {
    // « risques » n'a pas de page propre : il n'apparaît que s'il est le dernier segment.
    if (segment === "risques" && i < segments.length - 1) return;
    crumbs.push({
      to: `/${segments.slice(0, i + 1).join("/")}`,
      label: labelFor(segment, segments[i - 1]),
      // « etapes » n'a pas de page propre : simple libellé intermédiaire.
      linkable: !(segment === "etapes" && i < segments.length - 1),
    });
  });
  return crumbs;
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = crumbsFor(pathname);
  return (
    <Breadcrumb aria-label={fr.common.breadcrumb}>
      <BreadcrumbList className="gap-2 text-sm sm:gap-2">
        {crumbs.map((crumb, i) => {
          const last = i === crumbs.length - 1;
          return (
            <BreadcrumbItem key={crumb.to} className="gap-2">
              {last ? (
                <span aria-current="page" className="font-medium text-foreground">
                  {crumb.label}
                </span>
              ) : !crumb.linkable ? (
                <span className="text-text-muted">{crumb.label}</span>
              ) : (
                <BreadcrumbLink
                  asChild
                  className="text-text-muted underline-offset-[3px] hover:text-text-muted hover:underline"
                >
                  <Link to={crumb.to}>{crumb.label}</Link>
                </BreadcrumbLink>
              )}
              {!last && <ChevronRight aria-hidden className="size-3.5 text-text-muted" />}
            </BreadcrumbItem>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
