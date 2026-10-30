import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw";

// jsdom n'implémente pas ResizeObserver, requis par les cases à cocher Radix dans un formulaire.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
// Machines lentes (jsdom + axe) : 1 s par défaut est trop court pour les premiers rendus, et le
// premier affichage d'une route chargée à la demande (import dynamique) compile sa page.
configure({ asyncUtilTimeout: 15000 });

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

// jsdom n'a pas ResizeObserver : Radix (Checkbox dans un formulaire) en a besoin.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;
