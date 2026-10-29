import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { fetchAllPages } from "./allPages";

describe("fetchAllPages", () => {
  it("follows next across two pages with the maximum page size", async () => {
    const seen: string[] = [];
    server.use(
      http.get(`${API_URL}/api/v1/things/`, ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.search);
        const page = url.searchParams.get("page");
        return HttpResponse.json(
          page === "1"
            ? { count: 3, next: "next", previous: null, results: [1, 2] }
            : { count: 3, next: null, previous: "prev", results: [3] },
        );
      }),
    );
    const data = await fetchAllPages<number>("things", { q: "x" });
    expect(data).toEqual({ results: [1, 2, 3], count: 3 });
    expect(seen).toEqual(["?q=x&page=1&page_size=200", "?q=x&page=2&page_size=200"]);
  });

  it("stops at an empty page even if next is set", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/things/`, () =>
        HttpResponse.json({ count: 5, next: "n", previous: null, results: [] }),
      ),
    );
    expect(await fetchAllPages("things")).toEqual({ results: [], count: 5 });
  });
});
