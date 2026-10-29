import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import { documentKeys, GENERATION_TIMEOUT_MESSAGE, useGenerateDocument, useVersion } from "./api";
import { aVersion, OBJET_ID, queryWrapper, VERSION_ID } from "./testUtils";

afterEach(() => vi.useRealTimers());

describe("useVersion", () => {
  it("polls every 2 s while EN_COURS then stops at PRETE", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
        calls += 1;
        return HttpResponse.json(
          calls < 3 ? aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE" }) : aVersion(),
        );
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useVersion(VERSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(calls).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(calls).toBe(2));
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(result.current.data?.statut).toBe("PRETE"));
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(calls).toBe(3);
  });

  it("gives up after 3 minutes with a timeout error", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
        calls += 1;
        return HttpResponse.json(aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE" }));
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useVersion(VERSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(calls).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 3000));
    await waitFor(() =>
      expect(result.current.timeoutError?.message).toBe(GENERATION_TIMEOUT_MESSAGE),
    );
    const after = calls;
    await act(() => vi.advanceTimersByTimeAsync(20_000));
    expect(calls).toBe(after);
  });
});

describe("useGenerateDocument", () => {
  it("posts type_document and objet, then invalidates available, documents and the detail", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/api/v1/documents/generate/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aVersion({ statut: "EN_ATTENTE" }), { status: 202 });
      }),
    );
    const { client, Wrapper } = queryWrapper();
    const spy = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useGenerateDocument(), { wrapper: Wrapper });
    await act(() =>
      result.current.mutateAsync({ type_document: "ORDRE_MISSION", objet: OBJET_ID }),
    );
    expect(body).toEqual({ type_document: "ORDRE_MISSION", objet: OBJET_ID });
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(documentKeys.availables());
    expect(keys).toContainEqual(documentKeys.lists());
    expect(keys).toContainEqual(documentKeys.document(aVersion().document));
  });
});
