import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import { missionKeys } from "../missions/keys";
import { analyseKeys, useMarcLines, useOrientationReport, useSaveMarcLine } from "./api";
import { aMarcLine, ANALYSE_MISSION_ID } from "./testUtils";

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, Wrapper };
}

describe("analyse api hooks", () => {
  it("useMarcLines queries /marc-lines/?mission=<id> and follows the pages", async () => {
    const pages: string[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/marc-lines/`, ({ request }) => {
        const url = new URL(request.url);
        pages.push(url.search);
        const page = url.searchParams.get("page");
        return HttpResponse.json(
          page === "1"
            ? { count: 2, next: "x", previous: null, results: [aMarcLine({ id: "a" })] }
            : { count: 2, next: null, previous: "x", results: [aMarcLine({ id: "b" })] },
        );
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useMarcLines(ANALYSE_MISSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results.map((l) => l.id)).toEqual(["a", "b"]);
    expect(pages).toHaveLength(2);
    expect(pages[0]).toContain(`mission=${ANALYSE_MISSION_ID}`);
  });

  it("useOrientationReport reads the report addressed by the mission id", async () => {
    let called = "";
    server.use(
      http.get(`${API_URL}/api/v1/orientation-reports/:id/`, ({ params }) => {
        called = String(params.id);
        return HttpResponse.json({ mission: ANALYSE_MISSION_ID });
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useOrientationReport(ANALYSE_MISSION_ID), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(called).toBe(ANALYSE_MISSION_ID);
  });

  it("useSaveMarcLine invalidates the analysis keys, the steps and the current step", async () => {
    server.use(http.post(`${API_URL}/api/v1/marc-lines/`, () => HttpResponse.json(aMarcLine())));
    const { client, Wrapper } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useSaveMarcLine(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({
        data: { mission: ANALYSE_MISSION_ID, risque: "44444444-4444-4444-8444-444444444444" },
      }),
    );
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(analyseKeys.mission(ANALYSE_MISSION_ID));
    expect(keys).toContainEqual(missionKeys.steps(ANALYSE_MISSION_ID));
    expect(keys).toContainEqual([...missionKeys.all, "step"]);
  });
});
