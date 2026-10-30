import type { components } from "@/api/schema";

type S = components["schemas"];

/** Fixtures typées : recopiées de `backend/tests/notifications/contrat_lot8.json` (lot 8 T11). */
export const NOTIFICATION_ID = "bbbbbbbb-1111-4111-8111-bbbbbbbbbbbb";

export const notificationFixture = {
  id: NOTIFICATION_ID,
  type: "ACTION_DECLAREE",
  titre: "Action déclarée réalisée",
  message: "L'action « Formaliser le rapprochement mensuel » attend votre vérification.",
  lien: "/recommandations/actions/55555555-5555-4555-8555-555555555555",
  lue: false,
  lue_le: null,
  created_at: "2026-10-29T09:00:00Z",
} satisfies S["Notification"];

export const notificationsPageFixture = {
  count: 1,
  next: null,
  previous: null,
  results: [notificationFixture],
} satisfies S["PaginatedNotificationList"];

export const compteurFixture = { count: 1 } satisfies S["Compte"];
