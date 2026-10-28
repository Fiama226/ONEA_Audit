import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import { exportRiskMap, referentielKeys, useRiskMapComparison, useRisks, useSaveRisk } from "./api";

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { Wrapper, client };
}

describe("referentiel api hooks", () => {
  it("useRisks calls /risks/ with filters in the query string", async () => {
    let search = "";
    server.use(
      http.get(`${API_URL}/api/v1/risks/`, ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useRisks({ version: "v1", probabilite: 3, impact: 5 }), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(search).toBe("?version=v1&probabilite=3&impact=5");
  });

  it("useRiskMapComparison is disabled without a target version", () => {
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useRiskMapComparison("a", undefined), {
      wrapper: Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("useSaveRisk POSTs without id, PATCHes with id, and invalidates risks, matrices and maps", async () => {
    const calls: string[] = [];
    server.use(
      http.post(`${API_URL}/api/v1/risks/`, () => {
        calls.push("POST");
        return HttpResponse.json({ id: "r1" }, { status: 201 });
      }),
      http.patch(`${API_URL}/api/v1/risks/r1/`, () => {
        calls.push("PATCH");
        return HttpResponse.json({ id: "r1" });
      }),
    );
    const { Wrapper, client } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useSaveRisk(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({
        data: {
          version: "v",
          processus: "p",
          libelle: "x",
          probabilite: 1,
          impact: 1,
        },
      }),
    );
    await act(() => result.current.mutateAsync({ id: "r1", data: { libelle: "y" } }));
    expect(calls).toEqual(["POST", "PATCH"]);
    const keys = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(referentielKeys.risks()));
    expect(keys).toContain(JSON.stringify(referentielKeys.matrices()));
    expect(keys).toContain(JSON.stringify(referentielKeys.riskMaps()));
  });

  it("exportRiskMap requests the export action with ?type=csv", async () => {
    let search = "";
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/v9/export/`, ({ request }) => {
        search = new URL(request.url).search;
        return new HttpResponse("a", {
          headers: { "Content-Disposition": 'attachment; filename="c.csv"' },
        });
      }),
    );
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => {};
    await exportRiskMap("v9", "csv");
    expect(search).toBe("?type=csv");
  });
});
