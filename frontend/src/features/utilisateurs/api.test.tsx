import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { useAccountAction, useDirectionOptions, useImportCsv } from "./api";
import { useUserHistory } from "./history";
import { directionLabel } from "./labels";
import { aReport, anAccount } from "./testUtils";

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { Wrapper, client };
}

describe("useAccountAction", () => {
  it("posts the motif then invalidates the history query", async () => {
    let body: unknown;
    let historyCalls = 0;
    server.use(
      http.post(`${API_URL}/api/v1/user-accounts/7/deactivate/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(anAccount());
      }),
      http.get(`${API_URL}/api/v1/audit-log/`, () => {
        historyCalls += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );
    const { Wrapper } = wrapper();
    const both = renderHook(() => ({ h: useUserHistory(7, 1), a: useAccountAction() }), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(both.result.current.h.isSuccess).toBe(true));
    await act(() =>
      both.result.current.a.mutateAsync({ id: 7, action: "deactivate", motif: "Départ" }),
    );
    expect(body).toEqual({ motif: "Départ" });
    await waitFor(() => expect(historyCalls).toBe(2));
  });

  it("sends disable-otp as a POST without body", async () => {
    let method = "";
    let text = "x";
    server.use(
      http.post(`${API_URL}/api/v1/user-accounts/7/disable-otp/`, async ({ request }) => {
        method = request.method;
        text = await request.text();
        return HttpResponse.json(anAccount());
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useAccountAction(), { wrapper: Wrapper });
    await act(() => result.current.mutateAsync({ id: 7, action: "disable-otp" }));
    expect(method).toBe("POST");
    expect(text).toBe("");
  });
});

describe("useImportCsv", () => {
  it("sends multipart FormData and invalidates only when not a dry run", async () => {
    let contentType: string | null = null;
    let form: FormData | undefined;
    server.use(
      http.post(`${API_URL}/api/v1/user-accounts/import-csv/`, async ({ request }) => {
        contentType = request.headers.get("content-type");
        form = await request.formData();
        return HttpResponse.json(aReport());
      }),
    );
    const { Wrapper, client } = wrapper();
    client.setQueryData(["utilisateurs", "list", {}], { count: 0 });
    const { result } = renderHook(() => useImportCsv(), { wrapper: Wrapper });
    const file = new File(["a;b"], "c.csv", { type: "text/csv" });
    await act(() => result.current.mutateAsync({ file, dryRun: true, sendEmail: true }));
    expect(contentType).toMatch(/^multipart\/form-data/);
    expect(form?.get("dry_run")).toBe("true");
    expect(form?.get("envoyer_courriel")).toBe("true");
    expect(form?.get("fichier")).toMatchObject({ size: 3, type: "text/csv" });
    expect(client.getQueryState(["utilisateurs", "list", {}])?.isInvalidated).toBe(false);
    await act(() => result.current.mutateAsync({ file, dryRun: false, sendEmail: false }));
    expect(client.getQueryState(["utilisateurs", "list", {}])?.isInvalidated).toBe(true);
  });
});

describe("useDirectionOptions", () => {
  it("flags incomplete when the server has more than 200 directions", async () => {
    let search = "";
    server.use(
      http.get(`${API_URL}/api/v1/directions/`, ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json({ count: 201, next: "more", previous: null, results: [] });
      }),
    );
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useDirectionOptions(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.incomplete).toBe(true);
    expect(search).toBe("?page_size=200&ordering=code");
  });
});

describe("directionLabel", () => {
  it("covers known, unknown and empty codes", () => {
    expect(directionLabel("DAI", "Département Audit Interne")).toBe(
      "DAI — Département Audit Interne",
    );
    expect(directionLabel("DEX", null)).toBe("DEX (inconnue du référentiel)");
    expect(directionLabel("", null)).toBe("Non renseignée");
  });
});
