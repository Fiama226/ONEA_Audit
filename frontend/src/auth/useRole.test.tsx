import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { fakeMe, serveSession } from "@/test/auth";
import { AuthProvider } from "./AuthProvider";
import { RequireRole } from "./RequireRole";
import { useAuth } from "./useAuth";
import { useRole } from "./useRole";

function Probe() {
  const { status } = useAuth();
  const { role, is } = useRole();
  if (status !== "authenticated") return <p>attente</p>;
  return (
    <p>
      role={role} rai={String(is("RAI"))} dg={String(is("DG", "ADMIN"))}
    </p>
  );
}

function wrap(children: ReactNode) {
  render(
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>,
  );
}

describe("useRole", () => {
  it("is() est vrai pour le rôle RAI", async () => {
    serveSession(fakeMe({ role: "RAI" }));
    wrap(<Probe />);
    expect(await screen.findByText(/role=RAI rai=true dg=false/)).toBeInTheDocument();
  });

  it("traite un rôle inconnu comme AUDITE", async () => {
    serveSession(fakeMe({ role: "SUPERHERO" }));
    wrap(<Probe />);
    expect(await screen.findByText(/role=AUDITE rai=false/)).toBeInTheDocument();
  });
});

describe("RequireRole", () => {
  it("rend le contenu si le rôle correspond", async () => {
    serveSession(fakeMe({ role: "RAI" }));
    wrap(<RequireRole roles={["RAI"]}>contenu secret</RequireRole>);
    expect(await screen.findByText("contenu secret")).toBeInTheDocument();
  });

  it("rend le message d'interdiction sinon", async () => {
    serveSession(fakeMe({ role: "AUDITE" }));
    wrap(<RequireRole roles={["RAI"]}>contenu secret</RequireRole>);
    expect(await screen.findByText(fr.errors.forbiddenText)).toBeInTheDocument();
    expect(screen.queryByText("contenu secret")).not.toBeInTheDocument();
  });
});
