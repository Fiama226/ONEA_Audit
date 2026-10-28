import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import {
  exportRiskMap,
  fetchAllRisks,
  referentielKeys,
  useRiskMapComparison,
  useRisks,
  useSaveAuditableObject,
  useSaveRisk,
  useUpdateRiskMap,
} from "./api";

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

  it("useRisks keeps previous rows for the same version but not those of another version", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/risks/`, async ({ request }) => {
        const url = new URL(request.url);
        await new Promise((r) => setTimeout(r, 30));
        const v = url.searchParams.get("version");
        const q = url.searchParams.get("q") ?? "";
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [{ id: `${v}-${q}` }],
        });
      }),
    );
    const { Wrapper } = wrapper();
    const { result, rerender } = renderHook(
      ({ version, q }: { version: string; q?: string }) => useRisks({ version, q }),
      { wrapper: Wrapper, initialProps: { version: "A" } as { version: string; q?: string } },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    rerender({ version: "A", q: "x" });
    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.results[0]).toMatchObject({ id: "A-" });
    await waitFor(() => expect(result.current.isPlaceholderData).toBe(false));
    rerender({ version: "B" });
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.data?.results[0]).toMatchObject({ id: "B-" }));
  });

  it("fetchAllRisks follows pages and stops at the page cap", async () => {
    let calls = 0;
    server.use(
      http.get(`${API_URL}/api/v1/risks/`, () => {
        calls += 1;
        return HttpResponse.json({
          count: 999,
          next: "more",
          previous: null,
          results: [{ id: `r${calls}` }],
        });
      }),
    );
    const all = await fetchAllRisks({ version: "A" });
    expect(all).toHaveLength(50);
    expect(calls).toBe(50);
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

  describe("exportRiskMap", () => {
    function spyDownload() {
      const originalCreate = URL.createObjectURL;
      const originalRevoke = URL.revokeObjectURL;
      URL.createObjectURL = () => "blob:x";
      URL.revokeObjectURL = () => {};
      const names: string[] = [];
      const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
        this: HTMLAnchorElement,
      ) {
        names.push(this.download);
      });
      return {
        names,
        restore() {
          click.mockRestore();
          URL.createObjectURL = originalCreate;
          URL.revokeObjectURL = originalRevoke;
        },
      };
    }

    it("requests the export action with ?type=csv and saves under the server filename", async () => {
      let search = "";
      server.use(
        http.get(`${API_URL}/api/v1/risk-maps/v9/export/`, ({ request }) => {
          search = new URL(request.url).search;
          return new HttpResponse("a", {
            headers: { "Content-Disposition": 'attachment; filename="c.csv"' },
          });
        }),
      );
      const spy = spyDownload();
      try {
        await exportRiskMap("v9", "csv");
        expect(search).toBe("?type=csv");
        expect(spy.names).toEqual(["c.csv"]);
      } finally {
        spy.restore();
      }
    });

    it("falls back to cartographie.<type> when the filename header is unreadable", async () => {
      server.use(http.get(`${API_URL}/api/v1/risk-maps/v9/export/`, () => new HttpResponse("a")));
      const spy = spyDownload();
      try {
        await exportRiskMap("v9", "xlsx");
        expect(spy.names).toEqual(["cartographie.xlsx"]);
      } finally {
        spy.restore();
      }
    });
  });

  it.each([
    ["useSaveAuditableObject", "auditable-objects", "POST"],
    ["useUpdateRiskMap", "risk-maps/m1", "PATCH"],
  ] as const)("%s also invalidates risks", async (name, path, method) => {
    server.use(
      http.post(`${API_URL}/api/v1/${path}/`, () =>
        HttpResponse.json({ id: "x" }, { status: 201 }),
      ),
      http.patch(`${API_URL}/api/v1/${path}/`, () => HttpResponse.json({ id: "x" })),
    );
    const { Wrapper, client } = wrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    if (name === "useSaveAuditableObject") {
      const { result } = renderHook(() => useSaveAuditableObject(), { wrapper: Wrapper });
      await act(() =>
        result.current.mutateAsync({
          data: { processus: "p", nature: "DOMAINE", libelle: "d" },
        }),
      );
    } else {
      const { result } = renderHook(() => useUpdateRiskMap(), { wrapper: Wrapper });
      await act(() => result.current.mutateAsync({ id: "m1", data: { libelle: "v" } }));
    }
    expect(method).toBeTruthy();
    const keys = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(referentielKeys.risks()));
    if (name === "useUpdateRiskMap") {
      expect(keys.some((k) => k.includes("comparisons"))).toBe(true);
    }
  });
});
