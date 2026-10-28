import { describe, expect, it } from "vitest";
import { toQuery } from "./query";

describe("toQuery", () => {
  it("omits empty values, encodes and prefixes with ?", () => {
    expect(toQuery({ a: 1, b: undefined, q: "é" })).toBe("?a=1&q=%C3%A9");
  });
  it("returns an empty string when nothing remains", () => {
    expect(toQuery({ a: null, b: "", c: undefined })).toBe("");
  });
  it("keeps zero", () => {
    expect(toQuery({ page: 0 })).toBe("?page=0");
  });
});
