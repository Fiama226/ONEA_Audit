import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { components } from "@/api/schema";
import { toQuery } from "@/api/query";
import { notificationKeys } from "./keys";

type S = components["schemas"];
export type Notification = S["Notification"];
export type TypeNotification = S["TypeNotificationEnum"];
export type NotificationPage = S["PaginatedNotificationList"];

const BASE = "/api/v1/notifications";

export type NotificationParams = { non_lues?: boolean; page?: number; page_size?: number };

/** Intervalle de rafraîchissement du compteur : 60 s, suspendu quand l'onglet est caché. */
export const UNREAD_REFETCH_MS = 60_000;

export function unreadRefetchInterval(): number | false {
  return typeof document !== "undefined" && document.visibilityState === "hidden"
    ? false
    : UNREAD_REFETCH_MS;
}

export function useNotifications(params: NotificationParams = {}) {
  return useQuery({
    queryKey: notificationKeys.list(params),
    queryFn: () =>
      apiFetch<NotificationPage>(
        `${BASE}/${toQuery({
          non_lues: params.non_lues ? "true" : undefined,
          page: params.page,
          page_size: params.page_size,
        })}`,
      ),
    placeholderData: keepPreviousData,
  });
}

/** Compteur de la cloche : actualisé toutes les minutes et au retour sur l'onglet. */
export function useUnreadCount() {
  return useQuery({
    queryKey: notificationKeys.unread,
    queryFn: () => apiFetch<S["Compte"]>(`${BASE}/unread-count/`),
    refetchInterval: unreadRefetchInterval,
    refetchOnWindowFocus: true,
  });
}

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Notification>(`${BASE}/${id}/read/`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

export function useMarkAllRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<S["Compte"]>(`${BASE}/read-all/`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}
