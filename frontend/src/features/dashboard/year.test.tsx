import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Role } from "@/auth/types";
import { renderWithAuth } from "@/test/shell";
import { currentYear } from "./year";
import { DashboardPage } from "./pages/DashboardPage";

afterEach(() => vi.useRealTimers());

describe("currentYear", () => {
  it("uses the Ouagadougou calendar year", () => {
    expect(currentYear(new Date("2026-12-31T23:30:00Z"))).toBe(2026);
    expect(currentYear(new Date("2027-01-01T00:00:00Z"))).toBe(2027);
  });
});

describe("programme year", () => {
  it.each<Role>(["RAI", "AUDITEUR", "AUDITE", "DG"])("%s dashboard shows 2027", (role) => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2027-03-01T10:00:00Z"));
    renderWithAuth(<DashboardPage />, role);
    expect(screen.getAllByText(/Programme 2027/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Programme 2026/)).not.toBeInTheDocument();
  });
});
