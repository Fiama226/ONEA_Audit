import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadBlob } from "./download";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("downloadBlob", () => {
  it("clicks a hidden link named after the file, then revokes the URL later", () => {
    vi.useFakeTimers();
    const create = vi.fn(() => "blob:x");
    const revoke = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }));
    let download = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      download = this.download;
    });
    downloadBlob(new Blob(["a"]), "cartographie-2026.csv");
    expect(download).toBe("cartographie-2026.csv");
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:x");
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
