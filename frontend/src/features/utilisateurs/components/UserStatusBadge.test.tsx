import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { UserStatusBadge } from "./UserStatusBadge";

describe("UserStatusBadge", () => {
  it("shows the status as text", () => {
    const { rerender } = render(<UserStatusBadge active />);
    expect(screen.getByText("Actif")).toBeInTheDocument();
    rerender(<UserStatusBadge active={false} />);
    expect(screen.getByText("Désactivé")).toBeInTheDocument();
    rerender(<UserStatusBadge active pendingFirstLogin />);
    expect(screen.getByText("En attente de première connexion")).toBeInTheDocument();
  });
});
