import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import {
  planKeys,
  useAuditPlanLines,
  useDeleteAuditPlan,
  useSaveAuditPlanLine,
  useValidateAuditPlan,
} from "./api";
import { aLine, aPlan, aSummary, LINE_ID, PLAN_ID } from "./testUtils";

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { Wrapper, client };
}

describe("programmation api hooks", () => {
  it("useAuditPlanLines requests the plan with page_size=200 and follows two pages", async () => {
    const searches: string[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/audit-plan-lines/`, ({ request }) => {
        const url = new URL(request.url);
        searches.push(url.search);
        const first = url.searchParams.get("page") === "1";
        return HttpResponse.json({
          count: 2,
          next: first ? "more" : null,
          previous: null,
          results: [aLine({ id: first ? "a" : "b", numero: first ? 1 : 2 })],
        });
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useAuditPlanLines(PLAN_ID), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results.map((l) => l.id)).toEqual(["a", "b"]);
    expect(searches).toHaveLength(2);
    expect(searches[0]).toBe(`?programme=${PLAN_ID}&page=1&page_size=200`);
  });

  it("useSaveAuditPlanLine invalidates lines, plan detail and summary", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, () => HttpResponse.json(aLine())),
      http.patch(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () =>
        HttpResponse.json(aLine()),
      ),
    );
    const { Wrapper, client } = wrapper();
    client.setQueryData(planKeys.plan(PLAN_ID), aPlan());
    client.setQueryData(planKeys.summary(PLAN_ID), aSummary());
    client.setQueryData(planKeys.lines(PLAN_ID, {}), { results: [], count: 0 });
    client.setQueryData(planKeys.plan("other"), aPlan());
    const { result } = renderHook(() => useSaveAuditPlanLine(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({
        id: LINE_ID,
        data: { titre: "Nouveau titre" },
      }),
    );
    for (const key of [
      planKeys.plan(PLAN_ID),
      planKeys.summary(PLAN_ID),
      planKeys.lines(PLAN_ID, {}),
    ]) {
      expect(client.getQueryState(key)?.isInvalidated, JSON.stringify(key)).toBe(true);
    }
  });

  it("useSaveAuditPlanLine POSTs without id and PATCHes with one", async () => {
    const methods: string[] = [];
    server.use(
      http.post(`${API_URL}/api/v1/audit-plan-lines/`, () => {
        methods.push("POST");
        return HttpResponse.json(aLine());
      }),
      http.patch(`${API_URL}/api/v1/audit-plan-lines/${LINE_ID}/`, () => {
        methods.push("PATCH");
        return HttpResponse.json(aLine());
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useSaveAuditPlanLine(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({
        data: {
          programme: PLAN_ID,
          titre: "T",
          type: "CONSEIL",
          processus: "p",
          debut_prevu: "2026-01-01",
          fin_prevue: "2026-01-02",
        },
      }),
    );
    await act(() => result.current.mutateAsync({ id: LINE_ID, data: { titre: "U" } }));
    expect(methods).toEqual(["POST", "PATCH"]);
  });

  it("validating or deleting a plan also invalidates the plan list", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/audit-plans/${PLAN_ID}/validate/`, () =>
        HttpResponse.json(aPlan({ statut: "VALIDE" })),
      ),
      http.delete(
        `${API_URL}/api/v1/audit-plans/${PLAN_ID}/`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    const { Wrapper, client } = wrapper();
    const listKey = planKeys.plans({ annee: 2026 });
    client.setQueryData(listKey, { results: [] });
    const validate = renderHook(() => useValidateAuditPlan(), { wrapper: Wrapper });
    await act(() => validate.result.current.mutateAsync(PLAN_ID));
    expect(client.getQueryState(listKey)?.isInvalidated).toBe(true);

    client.setQueryData(listKey, { results: [] });
    const del = renderHook(() => useDeleteAuditPlan(), { wrapper: Wrapper });
    await act(() => del.result.current.mutateAsync(PLAN_ID));
    expect(client.getQueryState(listKey)?.isInvalidated).toBe(true);
  });
});
