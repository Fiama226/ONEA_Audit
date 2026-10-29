import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aDocument, aVersion, HASH, renderDocuments, VERSION_ID } from "../testUtils";
import { VersionHistory } from "./VersionHistory";

const d = fr.documents;

describe("VersionHistory", () => {
  it("lists versions with template, shortened hash and download count", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/consultations/`, () =>
        HttpResponse.json({ count: 2, next: null, previous: null, results: [] }),
      ),
    );
    const { container } = renderDocuments(<VersionHistory document={aDocument()} />);
    const row = screen.getByRole("row", { name: /v1/ });
    expect(within(row).getByText("v3 · provisoire")).toBeInTheDocument();
    expect(within(row).getByText("Prête")).toBeInTheDocument();
    expect(within(row).getByText("Awa Ouedraogo")).toBeInTheDocument();
    const code = within(row).getByText(`${HASH.slice(0, 8)}…${HASH.slice(-4)}`);
    expect(code).toHaveAttribute("title", HASH);
    expect(await within(row).findByText("2")).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("copies the full hash", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/consultations/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderDocuments(<VersionHistory document={aDocument({ versions: [aVersion()] })} />);
    await user.click(screen.getByRole("button", { name: d.copyHash }));
    expect(writeText).toHaveBeenCalledWith(HASH);
    expect(await screen.findByText(d.hashCopied)).toBeInTheDocument();
  });
});
