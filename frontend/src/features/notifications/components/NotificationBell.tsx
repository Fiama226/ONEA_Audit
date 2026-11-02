import { Bell } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fr } from "@/i18n/fr";
import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from "../api";
import { NotificationContent, safeLink } from "./NotificationList";

const MENU_SIZE = 10;
const T = fr.rechercheNotifications;

function BellMenuBody({ close }: { close: () => void }) {
  const navigate = useNavigate();
  const list = useNotifications({ page_size: MENU_SIZE });
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  if (list.isPending) {
    return (
      <p role="status" className="px-3 py-4 text-sm text-text-muted">
        {T.loadingMenu}
      </p>
    );
  }
  if (list.isError) {
    return (
      <p role="alert" className="px-3 py-4 text-sm text-destructive">
        {T.loadErrorMenu}
      </p>
    );
  }
  const items = list.data.results.slice(0, MENU_SIZE);
  return (
    <>
      {items.length === 0 ? (
        <p className="px-3 py-4 text-sm text-text-muted">{T.emptyMenu}</p>
      ) : (
        <div className="max-h-96 overflow-y-auto">
          {items.map((n) => (
            <DropdownMenuItem
              key={n.id}
              className="items-start py-2"
              onSelect={() => {
                const target = safeLink(n.lien);
                markRead
                  .mutateAsync(n.id)
                  .catch(() => undefined)
                  .finally(() => {
                    if (target) navigate(target);
                  });
                close();
              }}
            >
              <NotificationContent notification={n} />
            </DropdownMenuItem>
          ))}
        </div>
      )}
      <DropdownMenuSeparator />
      <DropdownMenuItem
        disabled={markAll.isPending || items.every((n) => n.lue)}
        onSelect={(e) => {
          e.preventDefault();
          markAll.mutate();
        }}
      >
        {T.markAllRead}
      </DropdownMenuItem>
      {markAll.isError && (
        <p role="alert" className="px-2 py-1 text-xs text-destructive">
          {T.markAllError}
        </p>
      )}
      <DropdownMenuItem asChild>
        <Link to="/notifications" onClick={close}>
          {T.seeAll}
        </Link>
      </DropdownMenuItem>
    </>
  );
}

/** Cloche de l'en-tête : compteur annoncé, pastille 9+, menu des 10 dernières notifications. */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const count = unread.data?.count ?? 0;
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        data-tour="notifications"
        aria-label={T.bellLabel.replace("{n}", String(count))}
        className="relative inline-flex size-9 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none data-[state=open]:bg-surface-subtle"
      >
        <Bell className="size-5" strokeWidth={1.5} aria-hidden />
        {count > 0 && (
          <span
            aria-hidden
            className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] leading-none font-semibold text-primary-foreground"
          >
            {count > 9 ? T.unreadBadgeMax : count}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-[360px] max-w-[95vw] bg-surface p-1"
      >
        <DropdownMenuLabel>{T.bellMenuTitle}</DropdownMenuLabel>
        <BellMenuBody close={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
