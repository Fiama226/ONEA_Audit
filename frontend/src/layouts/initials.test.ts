import { describe, expect, it } from "vitest";
import { initialsOf } from "./initials";

describe("initialsOf", () => {
  it.each([
    ["Awa", "Ouedraogo", "awa", "AO"],
    ["  awa ", " ouedraogo  ", "x", "AO"],
    ["", "Ouedraogo", "x", "O"],
    ["", "", "jdupont", "JD"],
    ["", "", "", "?"],
    ["   ", "   ", "  ", "?"],
    [null, undefined, undefined, "?"],
    ["Élodie", "Zongo", "e", "ÉZ"],
    ["élodie", "Zongo", "e", "ÉZ"],
  ] as const)("(%j, %j, %j) -> %s", (first, last, username, expected) => {
    expect(initialsOf(first, last, username)).toBe(expected);
  });
});
