import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useMarkAllRead, useMarkRead, useNotifications, type Notification } from "../api";
import { NotificationList, safeLink } from "../components/NotificationList";

const PAGE_SIZE = 20;
const T = fr.rechercheNotifications;

export function NotificationsPage() {
  const navigate = useNavigate();
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [page, setPage] = useState(1);
  const list = useNotifications({ non_lues: onlyUnread, page, page_size: PAGE_SIZE });
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  const open = (n: Notification) => {
    const target = safeLink(n.lien);
    markRead
      .mutateAsync(n.id)
      .catch(() => undefined)
      .finally(() => {
        if (target) navigate(target);
      });
  };
  const toggle = (value: boolean) => {
    setOnlyUnread(value);
    setPage(1);
  };

  const total = list.data ? Math.max(1, Math.ceil(list.data.count / PAGE_SIZE)) : 1;

  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">
        {fr.suivi.notificationsTitle}
      </h1>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div role="group" aria-label={T.filterLabel} className="flex gap-1">
          <Button
            type="button"
            size="sm"
            variant={onlyUnread ? "outline" : "secondary"}
            aria-pressed={!onlyUnread}
            onClick={() => toggle(false)}
          >
            {T.allNotifications}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={onlyUnread ? "secondary" : "outline"}
            aria-pressed={onlyUnread}
            onClick={() => toggle(true)}
          >
            {T.onlyUnread}
          </Button>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ml-auto"
          disabled={markAll.isPending}
          onClick={() => markAll.mutate()}
        >
          {T.markAllRead}
        </Button>
      </div>
      {markAll.isError && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {T.markAllError}
        </p>
      )}
      {list.isPending ? (
        <p role="status" className="text-sm text-text-muted">
          {T.loadingMenu}
        </p>
      ) : list.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {T.loadError}
        </p>
      ) : list.data.results.length === 0 ? (
        <p className="text-sm text-text-muted">{onlyUnread ? T.emptyUnread : T.emptyAll}</p>
      ) : (
        <>
          <div className="rounded-md border border-border bg-surface">
            <NotificationList items={list.data.results} onOpen={open} />
          </div>
          <nav aria-label={T.paginationLabel} className="mt-4 flex items-center gap-3">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {T.previousPage}
            </Button>
            <span className="text-sm text-text-muted">
              {T.pageOf.replace("{page}", String(page)).replace("{total}", String(total))}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!list.data.next}
              onClick={() => setPage((p) => p + 1)}
            >
              {T.nextPage}
            </Button>
          </nav>
        </>
      )}
    </>
  );
}
