import { Outlet, useLocation } from "react-router-dom";
import { LiveMessage } from "@/auth/LiveMessage";
import { PASSWORD_CHANGED_NOTICE, stateField } from "@/auth/paths";
import { fr } from "@/i18n/fr";
import { TutorielProvider } from "@/features/tutoriel/TutorielProvider";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { useDocumentTitle } from "./useDocumentTitle";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

/** Coque applicative : barre latérale (≥ 1024 px) ou tiroir, en-tête, zone principale. */
export function AppShell() {
  useDocumentTitle();
  const [collapsed, toggle] = useSidebarCollapsed();
  const location = useLocation();
  const passwordChanged = stateField(location.state, "notice") === PASSWORD_CHANGED_NOTICE;
  return (
    <TutorielProvider>
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
              {/* Confirmation d'un changement de mot de passe : la zone est rendue vide puis
                  remplie (LiveMessage), donc annoncée. */}
              {passwordChanged && (
                <LiveMessage
                  role="status"
                  message={fr.auth.passwordChanged}
                  className="mb-6 rounded-md border border-success/40 p-3 text-sm text-success-text print:hidden"
                />
              )}
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </TutorielProvider>
  );
}
