import { NavLink, Outlet } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";

const TABS = [
  { to: "cartographies", label: fr.referentiel.tabCartographies },
  { to: "processus", label: fr.referentiel.tabProcessus },
  { to: "directions", label: fr.referentiel.tabDirections },
  { to: "objets-auditables", label: fr.referentiel.tabObjets },
] as const;

export function ReferentielLayout() {
  return (
    <>
      <h1 className="mb-4 text-2xl font-semibold tracking-[-0.012em]">{fr.referentiel.title}</h1>
      <nav
        aria-label={fr.referentiel.tabsLabel}
        className="mb-6 border-b border-border print:hidden"
      >
        <ul className="-mb-px flex flex-wrap gap-x-6">
          {TABS.map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                className={({ isActive }) =>
                  cn(
                    "inline-flex h-11 items-center border-b-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring",
                    isActive
                      ? "border-primary text-foreground"
                      : "border-transparent text-text-muted hover:text-foreground",
                  )
                }
              >
                {tab.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <Outlet />
    </>
  );
}
