import { PanelLeftClose, PanelLeftOpen, type LucideIcon } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useAccountRights } from "@/auth/useAccountRights";
import { useRole } from "@/auth/useRole";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { navFor } from "./navigation";

/** Navigation principale, partagée par la barre latérale et le tiroir. */
export function SidebarNav({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { role } = useRole();
  const { canManage } = useAccountRights();
  const groups = navFor(role, canManage);

  return (
    <nav
      aria-label={fr.nav.primary}
      data-tour="menu-lateral"
      className="flex-1 overflow-y-auto px-3 pb-3"
    >
      {groups.map((group, index) => (
        <div key={group.title ?? index} className={cn(index > 0 && "mt-1")}>
          {group.title &&
            (collapsed ? (
              <>
                <h3 className="sr-only">{group.title}</h3>
                <div aria-hidden className="mx-2 mt-1 mb-2.5 h-px bg-border" />
              </>
            ) : (
              <h3 className="px-3 pt-3 pb-1.5 text-xs font-semibold tracking-[0.06em] text-text-muted uppercase">
                {group.title}
              </h3>
            ))}
          <ul className={cn("flex flex-col gap-0.5", collapsed && "items-center")}>
            {group.items.map((item) => (
              <li key={item.to} className={cn(collapsed && "w-10")}>
                <NavItemLink {...item} collapsed={collapsed} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

const TOUR_IDS: Record<string, string> = {
  "/": "nav-tableau-de-bord",
  "/administration/documents": "nav-gabarits",
  "/administration/signatures": "nav-signatures",
};

/** Repère de la visite guidée : `nav-<segment>` (voir features/tutoriel). */
const tourId = (to: string) => TOUR_IDS[to] ?? `nav-${to.slice(1)}`;

function NavItemLink({
  to,
  label,
  icon: Icon,
  collapsed,
  onNavigate,
  exclude,
}: {
  exclude?: string | string[];
  to: string;
  label: string;
  icon: LucideIcon;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  const excluded = [exclude ?? []].flat().some((prefix) => pathname.startsWith(prefix));
  const link = (
    <NavLink
      to={to}
      data-tour={tourId(to)}
      end={to === "/"}
      aria-current={excluded ? false : "page"}
      onClick={onNavigate}
      className={({ isActive: active }) =>
        cn(
          "relative flex items-center rounded-md text-sm font-medium transition-colors hover:bg-surface-subtle hover:[&_svg]:text-foreground",
          collapsed ? "size-10 justify-center" : "h-9 gap-3 px-3",
          active && !excluded
            ? "bg-primary/10 font-semibold text-primary hover:bg-primary/10"
            : "text-foreground",
        )
      }
    >
      {({ isActive: active }) => (
        <>
          {active && !excluded && (
            <span
              aria-hidden
              className="absolute top-2 bottom-2 -left-3 w-[3px] rounded-r-[2px] bg-brand-accent"
            />
          )}
          <Icon
            className={cn(
              "size-5 shrink-0",
              active && !excluded ? "text-primary" : "text-text-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className={cn(collapsed && "sr-only")}>{label}</span>
        </>
      )}
    </NavLink>
  );
  if (!collapsed) return link;
  return (
    <Tooltip delayDuration={300}>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={12}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

/** Barre latérale fixe (≥ 1024 px) : 260 px dépliée, 64 px repliée. */
export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;
  const toggleLabel = collapsed ? fr.shell.expandMenu : fr.shell.collapseMenu;
  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex h-full shrink-0 flex-col border-r border-border bg-surface",
          collapsed ? "w-16" : "w-[260px]",
        )}
      >
        <div
          className={cn(
            "flex h-14 shrink-0 items-center border-b border-border",
            collapsed ? "justify-center" : "px-5",
          )}
        >
          <Logo compact={collapsed} subtitle={fr.app.shortName} />
        </div>
        <div className="flex min-h-0 flex-1 flex-col pt-3">
          <SidebarNav collapsed={collapsed} />
        </div>
        <div
          className={cn(
            "flex h-14 shrink-0 items-center border-t border-border",
            collapsed ? "justify-center" : "justify-between px-5",
          )}
        >
          {!collapsed && <span className="text-xs text-text-muted">{fr.shell.version}</span>}
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={fr.shell.toggleMenu}
                aria-expanded={!collapsed}
                onClick={onToggle}
                className="text-text-muted hover:text-foreground"
              >
                <ToggleIcon className="size-5" strokeWidth={1.5} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={12}>
              {toggleLabel}
            </TooltipContent>
          </Tooltip>
        </div>
      </aside>
    </TooltipProvider>
  );
}
