import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime } from "./dates";

describe("formatDate", () => {
  it("formats an ISO instant as JJ/MM/AAAA in Africa/Ouagadougou", () => {
    expect(formatDate("2026-10-27T23:30:00Z")).toBe("27/10/2026");
  });
});

describe("formatDateTime", () => {
  it("formats as JJ/MM/AAAA HH:mm", () => {
    expect(formatDateTime("2026-10-27T23:30:00Z")).toBe("27/10/2026 23:30");
  });
});
