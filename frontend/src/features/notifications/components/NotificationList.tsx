import { formatDistanceToNowStrict } from "date-fns";
import { fr as frLocale } from "date-fns/locale";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import type { Notification } from "../api";

/** Destination interne d'une notification ; tout lien externe ou relatif au protocole est ignoré. */
export function safeLink(lien: string | undefined | null): string | null {
  if (!lien || !lien.startsWith("/") || lien.startsWith("//") || lien.includes("\\")) return null;
  return lien;
}

export function relativeDate(iso: string): string {
  return formatDistanceToNowStrict(new Date(iso), { addSuffix: true, locale: frLocale });
}

/** Contenu d'une notification : titre, message, date relative (date absolue en `title`). */
export function NotificationContent({ notification }: { notification: Notification }) {
  return (
    <span className="flex min-w-0 flex-col gap-0.5 text-left">
      <span className="flex items-center gap-2">
        <span className={notification.lue ? "font-normal" : "font-semibold"}>
          {notification.titre}
        </span>
        {!notification.lue && (
          <span className="rounded-sm bg-primary/10 px-1.5 text-xs text-primary">
            {fr.rechercheNotifications.unreadMark}
          </span>
        )}
      </span>
      <span className="text-sm text-text-muted">{notification.message}</span>
      <time
        dateTime={notification.created_at}
        title={formatDateTime(notification.created_at)}
        className="text-xs text-text-muted"
      >
        {relativeDate(notification.created_at)}
      </time>
    </span>
  );
}

/** Liste complète (page des notifications) : chaque notification est un bouton atteignable au clavier. */
export function NotificationList({
  items,
  onOpen,
}: {
  items: readonly Notification[];
  onOpen: (notification: Notification) => void;
}) {
  return (
    <ul aria-label={fr.rechercheNotifications.listLabel} className="divide-y divide-border">
      {items.map((n) => (
        <li key={n.id}>
          <button
            type="button"
            onClick={() => onOpen(n)}
            className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <NotificationContent notification={n} />
          </button>
        </li>
      ))}
    </ul>
  );
}
