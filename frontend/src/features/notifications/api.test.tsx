import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { queryWrapper } from "@/features/documents/testUtils";
import { useMarkAllRead, useNotifications, useUnreadCount } from "./api";
import { compteurFixture, notificationsPageFixture } from "./fixtures";

const BASE = `${API_URL}/api/v1/notifications`;

describe("en-tête d'arrière-plan", () => {
  it("le compteur de la cloche est une requête d'arrière-plan", async () => {
    let header: string | null = null;
    server.use(
      http.get(`${BASE}/unread-count/`, ({ request }) => {
        header = request.headers.get("X-Onea-Arriere-Plan");
        return HttpResponse.json(compteurFixture);
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useUnreadCount(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(header).toBe("1");
  });

  it("la liste et « tout marquer comme lu » (actions de l'agent) ne l'envoient pas", async () => {
    const headers: (string | null)[] = [];
    server.use(
      http.get(`${BASE}/`, ({ request }) => {
        headers.push(request.headers.get("X-Onea-Arriere-Plan"));
        return HttpResponse.json(notificationsPageFixture);
      }),
      http.post(`${BASE}/read-all/`, ({ request }) => {
        headers.push(request.headers.get("X-Onea-Arriere-Plan"));
        return HttpResponse.json(compteurFixture);
      }),
    );
    const { Wrapper } = queryWrapper();
    const list = renderHook(() => useNotifications(), { wrapper: Wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    const mark = renderHook(() => useMarkAllRead(), { wrapper: Wrapper });
    await mark.result.current.mutateAsync();
    // Liste, validation, puis relecture de la liste après invalidation : aucune n'est d'arrière-plan.
    expect(headers.length).toBeGreaterThanOrEqual(2);
    expect(headers.every((h) => h === null)).toBe(true);
  });
});
