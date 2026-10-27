import { Outlet } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

/** Coque applicative : barre latérale (≥ 1024 px) ou tiroir, en-tête, zone principale. */
export function AppShell() {
  const [collapsed, toggle] = useSidebarCollapsed();
  return (
    <>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        {fr.shell.skipToContent}
      </a>
      <div className="flex h-dvh bg-background print:block print:h-auto">
        <div className="hidden lg:block print:hidden">
          <Sidebar collapsed={collapsed} onToggle={toggle} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="print:hidden">
            <Header />
          </div>
          <main
            id="contenu"
            tabIndex={-1}
            className="flex-1 overflow-y-auto px-6 pt-6 pb-12 outline-none lg:px-8 lg:pt-8"
          >
            <div className="mx-auto max-w-[1280px]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
