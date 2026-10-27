import { describe, expect, it, vi } from "vitest";

const ctor = vi.fn();
vi.mock("oidc-client-ts", () => ({
  UserManager: class {
    constructor(settings: unknown) {
      ctor(settings);
    }
  },
  WebStorageStateStore: class {},
}));

describe("createUserManager", () => {
  it("utilise une URI de déconnexion avec barre finale (comme docs/deploy.md)", async () => {
    const { createUserManager } = await import("./oidc");
    createUserManager();
    const settings = ctor.mock.calls[0]?.[0] as Record<string, string> | undefined;
    expect(settings?.post_logout_redirect_uri).toBe(`${window.location.origin}/`);
    expect(settings?.redirect_uri).toBe(`${window.location.origin}/callback`);
  });
});
