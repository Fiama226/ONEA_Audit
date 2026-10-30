import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["notifications"] as const;

/** Clés TanStack Query des notifications ; `unread` est le compteur de la cloche. */
export const notificationKeys = {
  all: ROOT as QueryKey,
  list: (params?: object) => [...ROOT, "list", params ?? null] as QueryKey,
  unread: [...ROOT, "unread"] as QueryKey,
};
