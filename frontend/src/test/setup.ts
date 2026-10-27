import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "./msw";

// Le shell complet est lourd à monter sous jsdom : marge pour les attentes asynchrones.
configure({ asyncUtilTimeout: 4000 });
vi.setConfig({ testTimeout: 15000 });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());
