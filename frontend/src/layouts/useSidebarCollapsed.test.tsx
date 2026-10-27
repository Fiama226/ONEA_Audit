import { act, renderHook } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockMatchMedia } from "@/test/shell";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

const WIDE = "(min-width: 1280px)";
const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("useSidebarCollapsed", () => {
  it("writes the choice once per toggle, even in StrictMode", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { result } = renderHook(() => useSidebarCollapsed(), { wrapper });
    act(() => result.current[1]());
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(setItem).toHaveBeenCalledWith("onea.sidebar", "collapsed");
    expect(result.current[0]).toBe(true);
    act(() => result.current[1]());
    expect(setItem).toHaveBeenLastCalledWith("onea.sidebar", "expanded");
    expect(result.current[0]).toBe(false);
  });

  it("follows the viewport until the user toggles", () => {
    const media = mockMatchMedia({ [WIDE]: true });
    const { result } = renderHook(() => useSidebarCollapsed(), { wrapper });
    expect(result.current[0]).toBe(false);
    media.set(WIDE, false);
    expect(result.current[0]).toBe(true);
    media.set(WIDE, true);
    expect(result.current[0]).toBe(false);
    act(() => result.current[1]());
    expect(result.current[0]).toBe(true);
    media.set(WIDE, true);
    expect(result.current[0]).toBe(true);
  });

  it("ignores the viewport when a choice is stored", () => {
    const media = mockMatchMedia({ [WIDE]: true });
    localStorage.setItem("onea.sidebar", "expanded");
    const { result } = renderHook(() => useSidebarCollapsed(), { wrapper });
    media.set(WIDE, false);
    expect(result.current[0]).toBe(false);
  });
});
