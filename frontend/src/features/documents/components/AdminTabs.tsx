import { NavLink } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/administration/documents", label: fr.documents.tabTemplates, end: false },
  { to: "/administration/documents/numerotation", label: fr.documents.tabNumbering, end: true },
];

/** Navigation entre les écrans d'administration des documents. */
export function AdminTabs() {
  return (
    <nav aria-label={fr.documents.tabTemplates + " / " + fr.documents.tabNumbering}>
      <ul className="flex gap-4 border-b border-border">
        {LINKS.map((l) => (
          <li key={l.to}>
            <NavLink
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                cn(
                  "inline-block border-b-2 px-1 pb-2 text-sm font-medium",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-text-muted hover:text-foreground",
                )
              }
            >
              {l.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
