import { fireEvent, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BACKGROUND_HEADER } from "@/api/client";
import { API_URL, server } from "@/test/msw";
import {
  KEEP_ALIVE_INTERVAL_MS,
  keepAlivePing,
  useActivityKeepAlive,
} from "./useActivityKeepAlive";

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
}

describe("useActivityKeepAlive", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility("visible");
  });
  afterEach(() => {
    vi.useRealTimers();
    setVisibility("visible");
  });

  it("frappe pendant la saisie : une requête toutes les 10 minutes tant que l'agent agit", () => {
    const ping = vi.fn();
    renderHook(() => useActivityKeepAlive(true, ping));
    vi.advanceTimersByTime(60_000);
    fireEvent.keyDown(document.body, { key: "a" });
    vi.advanceTimersByTime(KEEP_ALIVE_INTERVAL_MS);
    expect(ping).toHaveBeenCalledTimes(1);
    fireEvent.pointerDown(document.body);
    vi.advanceTimersByTime(KEEP_ALIVE_INTERVAL_MS);
    expect(ping).toHaveBeenCalledTimes(2);
  });

  it("aucune activité : aucune requête (la session expire au bout de 30 minutes)", () => {
    const ping = vi.fn();
    renderHook(() => useActivityKeepAlive(true, ping));
    vi.advanceTimersByTime(4 * KEEP_ALIVE_INTERVAL_MS);
    expect(ping).not.toHaveBeenCalled();
  });

  it("une activité ne vaut qu'une fois : pas de requête suivante sans nouvelle activité", () => {
    const ping = vi.fn();
    renderHook(() => useActivityKeepAlive(true, ping));
    fireEvent.keyDown(document.body, { key: "a" });
    vi.advanceTimersByTime(3 * KEEP_ALIVE_INTERVAL_MS);
    expect(ping).toHaveBeenCalledTimes(1);
  });

  it("onglet masqué : aucune requête", () => {
    const ping = vi.fn();
    renderHook(() => useActivityKeepAlive(true, ping));
    fireEvent.keyDown(document.body, { key: "a" });
    setVisibility("hidden");
    vi.advanceTimersByTime(KEEP_ALIVE_INTERVAL_MS);
    expect(ping).not.toHaveBeenCalled();
  });

  it("désactivé (anonyme) ou démonté : aucune requête", () => {
    const ping = vi.fn();
    const { rerender, unmount } = renderHook(({ on }) => useActivityKeepAlive(on, ping), {
      initialProps: { on: false },
    });
    fireEvent.keyDown(document.body, { key: "a" });
    vi.advanceTimersByTime(KEEP_ALIVE_INTERVAL_MS);
    rerender({ on: true });
    unmount();
    fireEvent.keyDown(document.body, { key: "a" });
    vi.advanceTimersByTime(KEEP_ALIVE_INTERVAL_MS);
    expect(ping).not.toHaveBeenCalled();
  });
});

describe("keepAlivePing", () => {
  it("sonde la session SANS l'en-tête d'arrière-plan (compte comme une activité)", async () => {
    let entete: string | null = "absent";
    server.use(
      http.get(`${API_URL}/api/v1/auth/session/`, ({ request }) => {
        entete = request.headers.get(BACKGROUND_HEADER);
        return HttpResponse.json({ etape: "OK", me: { id: 1 } });
      }),
    );
    await keepAlivePing();
    expect(entete).toBeNull();
  });

  it("n'échoue jamais (un 401 est traité par la requête suivante)", async () => {
    await expect(keepAlivePing()).resolves.toBeUndefined();
  });
});
