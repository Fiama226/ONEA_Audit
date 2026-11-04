import { afterEach, describe, expect, it, vi } from "vitest";
import {
  announce,
  clearPendingLogout,
  hasPendingLogout,
  listen,
  markPendingLogout,
} from "./crossTab";

describe("signaux entre onglets", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("ignore ses propres annonces et reçoit celles d'un autre onglet", async () => {
    const recus: string[] = [];
    const stop = listen((type) => recus.push(type));
    announce("logout");
    const autre = new BroadcastChannel("onea-auth");
    autre.postMessage({ type: "login", from: "autre-onglet" });
    autre.postMessage({ type: "inconnu", from: "autre-onglet" });
    autre.close();
    await vi.waitFor(() => expect(recus).toEqual(["login"]));
    stop();
  });

  it("sans BroadcastChannel : repli sur l'événement storage, sans secret", () => {
    vi.stubGlobal("BroadcastChannel", undefined);
    const recus: string[] = [];
    const stop = listen((type) => recus.push(type));
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "onea-auth-signal",
        newValue: JSON.stringify({ type: "logout", from: "autre-onglet", at: 1 }),
      }),
    );
    expect(recus).toEqual(["logout"]);
    announce("login");
    const stocke = JSON.parse(localStorage.getItem("onea-auth-signal") ?? "{}") as object;
    expect(Object.keys(stocke).sort()).toEqual(["at", "from", "type"]);
    stop();
  });
});

describe("marque de déconnexion en attente", () => {
  it("une confirmation tardive n'efface pas la marque d'une déconnexion plus récente", () => {
    const ancienne = markPendingLogout();
    const recente = `${ancienne}-2`;
    localStorage.setItem("onea-deconnexion-en-attente", recente);
    clearPendingLogout(ancienne);
    expect(hasPendingLogout()).toBe(true);
    clearPendingLogout(recente);
    expect(hasPendingLogout()).toBe(false);
  });
});
