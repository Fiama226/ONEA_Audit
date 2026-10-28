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

/** Segments sans page propre : affichés dans le fil mais non cliquables. */
const NON_LINK_SEGMENTS = new Set(["risques"]);

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function labelFor(segment: string): string {
  if (UUID.test(segment)) return fr.referentiel.detail;
  return SEGMENT_LABELS[segment] ?? segment;
}

function crumbsFor(pathname: string): Crumb[] {
  const root: Crumb = { to: "/", label: fr.nav.dashboard, linkable: true };
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [root];
  const crumbs: Crumb[] = [root];
  segments.forEach((segment, i) => {
    crumbs.push({
      to: `/${segments.slice(0, i + 1).join("/")}`,
      label: labelFor(segment),
      linkable: !NON_LINK_SEGMENTS.has(segment),
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
