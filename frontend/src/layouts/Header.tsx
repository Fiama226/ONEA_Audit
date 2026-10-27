import { Menu, Search, X } from "lucide-react";
import { useState } from "react";
import { LogoMark } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
  SheetClose,
} from "@/components/ui/sheet";
import { fr } from "@/i18n/fr";
import { Breadcrumbs } from "./Breadcrumbs";
import { SidebarNav } from "./Sidebar";
import { UserMenu } from "./UserMenu";

export function Header() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-surface pr-6 pl-4 lg:pl-8">
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={fr.shell.openMenu}
            className="lg:hidden"
          >
            <Menu className="size-5" strokeWidth={1.5} aria-hidden />
          </Button>
        </SheetTrigger>
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-[280px] gap-0 bg-surface p-0 shadow-floating sm:max-w-[280px]"
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
            <SheetTitle className="sr-only">{fr.shell.mobileMenuTitle}</SheetTitle>
            <SheetDescription className="sr-only">{fr.app.tagline}</SheetDescription>
            <div className="flex items-center gap-3" aria-hidden>
              <LogoMark />
              <div className="flex flex-col leading-[1.15]">
                <span className="text-base font-bold tracking-[0.08em]">ONEA</span>
                <span className="mt-0.5 text-xs text-text-muted">{fr.app.shortName}</span>
              </div>
            </div>
            <SheetClose asChild>
              <Button type="button" variant="ghost" size="icon" aria-label={fr.shell.closeMenu}>
                <X className="size-5" strokeWidth={1.5} aria-hidden />
              </Button>
            </SheetClose>
          </div>
          <div className="flex min-h-0 flex-1 flex-col pt-3">
            <SidebarNav onNavigate={() => setDrawerOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex items-center gap-2.5 lg:hidden" aria-hidden>
        <LogoMark className="size-7" />
        <span className="text-sm font-bold tracking-[0.08em]">ONEA</span>
      </div>

      <div className="hidden min-w-0 flex-1 lg:block">
        <Breadcrumbs />
      </div>
      <div className="flex-1 lg:hidden" />

      <div className="relative hidden lg:block lg:w-60 xl:w-80">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <Input
          type="search"
          disabled
          aria-label={fr.shell.searchLabel}
          placeholder={fr.shell.searchPlaceholder}
          className="h-9 cursor-not-allowed rounded-md border-transparent bg-surface-subtle pl-9 text-text-muted placeholder:text-text-muted disabled:opacity-100"
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled
        aria-label={fr.shell.searchPlaceholder}
        className="cursor-not-allowed bg-surface-subtle text-text-muted disabled:opacity-100 lg:hidden"
      >
        <Search className="size-4" aria-hidden />
      </Button>

      <div className="h-6 w-px bg-border" aria-hidden />
      <UserMenu />
    </header>
  );
}
