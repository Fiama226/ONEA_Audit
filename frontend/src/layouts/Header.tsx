import { Menu, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/auth/useAuth";
import { NotificationBell } from "@/features/notifications/components/NotificationBell";
import { GlobalSearchInput } from "@/features/recherche/components/GlobalSearchInput";
import { fr } from "@/i18n/fr";
import { Breadcrumbs } from "./Breadcrumbs";
import { SidebarNav } from "./Sidebar";
import { UserMenu } from "./UserMenu";

const DESKTOP_QUERY = "(min-width: 1024px)";

/** Ferme le tiroir dès que la barre latérale fixe réapparaît (fenêtre ≥ 1024 px). */
function useCloseOnDesktop(close: () => void) {
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(DESKTOP_QUERY);
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) close();
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [close]);
}

export function Header() {
  const { me } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  useCloseOnDesktop(closeDrawer);
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-surface pr-6 pl-4 lg:pl-8">
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={fr.shell.openMenu}
            data-tour="menu-bouton"
            className="lg:hidden"
          >
            <Menu className="size-5" strokeWidth={1.5} aria-hidden />
          </Button>
        </SheetTrigger>
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-[280px] gap-0 bg-surface p-0 sm:max-w-[280px]"
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
            <SheetTitle className="sr-only">{fr.shell.mobileMenuTitle}</SheetTitle>
            <SheetDescription className="sr-only">{fr.app.tagline}</SheetDescription>
            <Logo subtitle={fr.app.shortName} />
            <SheetClose asChild>
              <Button type="button" variant="ghost" size="icon" aria-label={fr.shell.closeMenu}>
                <X className="size-5" strokeWidth={1.5} aria-hidden />
              </Button>
            </SheetClose>
          </div>
          <div className="flex min-h-0 flex-1 flex-col pt-3">
            <SidebarNav onNavigate={closeDrawer} />
          </div>
        </SheetContent>
      </Sheet>

      <Logo className="lg:hidden" />

      <div className="hidden min-w-0 flex-1 lg:block">
        <Breadcrumbs />
      </div>
      <div className="flex-1 lg:hidden" />

      {me?.role !== "ADMIN" && <GlobalSearchInput />}
      <NotificationBell />

      <div className="h-6 w-px bg-border" aria-hidden />
      <UserMenu />
    </header>
  );
}
