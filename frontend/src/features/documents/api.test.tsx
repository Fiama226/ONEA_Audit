import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_URL, server } from "@/test/msw";
import {
  documentKeys,
  GENERATION_TIMEOUT_MESSAGE,
  useAvailableDocuments,
  useGenerateDocument,
  useVersion,
} from "./api";
import { aDisponible, aVersion, MISSION_ID, OBJET_ID, queryWrapper, VERSION_ID } from "./testUtils";

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
    await act(() => vi.advanceTimersByTimeAsync(2500));
    const after = calls;
    await act(() => vi.advanceTimersByTimeAsync(20_000));
    expect(calls).toBe(after);
  });
});

describe("en-tête d'arrière-plan des interrogations", () => {
  it("useVersion : le premier chargement est celui de l'agent, les relectures d'interrogation sont d'arrière-plan", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const recus: (string | null)[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, ({ request }) => {
        recus.push(request.headers.get("X-Onea-Arriere-Plan"));
        return HttpResponse.json(
          recus.length < 3
            ? aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE" })
            : aVersion(),
        );
      }),
    );
    const { Wrapper } = queryWrapper();
    renderHook(() => useVersion(VERSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(recus).toHaveLength(1));
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(recus).toHaveLength(2));
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(recus).toHaveLength(3));
    expect(recus).toEqual([null, "1", "1"]);
  });

  it("useAvailableDocuments : relance manuelle = requête de l'agent", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const recus: (string | null)[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, ({ request }) => {
        recus.push(request.headers.get("X-Onea-Arriere-Plan"));
        return HttpResponse.json([aDisponible({ en_cours: true })]);
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useAvailableDocuments(MISSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(recus).toHaveLength(1));
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(recus).toHaveLength(2));
    await act(async () => result.current.restartPolling());
    await waitFor(() => expect(recus.length).toBeGreaterThanOrEqual(3));
    expect(recus.slice(0, 3)).toEqual([null, "1", null]);
  });
});

describe("polling budget", () => {
  it("polls again after a timeout once the version was regenerated on the same hook", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    let phase: "stuck" | "done" | "again" = "stuck";
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/`, () => {
        calls += 1;
        return HttpResponse.json(
          phase === "done"
            ? aVersion()
            : aVersion({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE" }),
        );
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useVersion(VERSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(calls).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 3000));
    await waitFor(() => expect(result.current.timeoutError).not.toBeNull());
    phase = "done";
    await act(() => result.current.refetch());
    await waitFor(() => expect(result.current.timeoutError).toBeNull());
    phase = "again";
    await act(() => result.current.refetch());
    const before = calls;
    await act(() => vi.advanceTimersByTimeAsync(2100));
    await waitFor(() => expect(calls).toBeGreaterThan(before));
    expect(result.current.timeoutError).toBeNull();
  });

  it("stops polling the available documents after 3 minutes and exposes the timeout", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      http.get(`${API_URL}/api/v1/documents/available/`, () => {
        calls += 1;
        return HttpResponse.json([aDisponible({ en_cours: true })]);
      }),
    );
    const { Wrapper } = queryWrapper();
    const { result } = renderHook(() => useAvailableDocuments(MISSION_ID), { wrapper: Wrapper });
    await waitFor(() => expect(calls).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(3 * 60 * 1000 + 3000));
    await waitFor(() =>
      expect(result.current.timeoutError?.message).toBe(GENERATION_TIMEOUT_MESSAGE),
    );
    await act(() => vi.advanceTimersByTimeAsync(2500));
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
