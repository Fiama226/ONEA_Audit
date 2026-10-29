import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import { missionKeys, useStepAction, useSteps } from "./api";
import { aStep, MISSION_ID } from "./testUtils";

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, Wrapper };
}

describe("mission api hooks", () => {
  it("useSteps calls /mission-steps/?mission=<id>", async () => {
    let url = "";
    server.use(
      http.get(`${API_URL}/api/v1/mission-steps/`, ({ request }) => {
        url = new URL(request.url).search;
        return HttpResponse.json([aStep()]);
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useSteps(MISSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(url).toBe(`?mission=${MISSION_ID}`);
  });

  it("useStepAction invalidates the mission detail, steps and tracking", async () => {
    const step = aStep({ id: "step-1", statut: "EN_COURS" });
    server.use(
      http.post(`${API_URL}/api/v1/mission-steps/step-1/start/`, () => HttpResponse.json(step)),
    );
    const { client, Wrapper } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useStepAction(), { wrapper: Wrapper });
    await act(() => result.current.mutateAsync({ id: "step-1", action: "start" }));
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(missionKeys.detail(MISSION_ID));
    expect(keys).toContainEqual(missionKeys.steps(MISSION_ID));
    expect(keys).toContainEqual(missionKeys.tracking(MISSION_ID));
    expect(keys).toContainEqual(missionKeys.lists());
  });

  it("sends the motif for actions that need one", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/mission-steps/step-1/return/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aStep({ id: "step-1" }));
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useStepAction(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({ id: "step-1", action: "return", motif: "Incomplet" }),
    );
    expect(body).toEqual({ motif: "Incomplet" });
  });
});
