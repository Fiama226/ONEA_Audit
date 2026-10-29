import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aVersion, renderDocuments, VERSION_ID } from "../testUtils";
import { DownloadButtons } from "./DownloadButtons";

const d = fr.documents;

afterEach(() => vi.restoreAllMocks());

describe("DownloadButtons", () => {
  it("disables the PDF button with the reason while the PDF is not ready", async () => {
    const { container } = renderDocuments(
      <DownloadButtons version={aVersion({ statut_pdf: "EN_COURS" })} />,
    );
    expect(screen.getByRole("button", { name: d.downloadWord })).toBeEnabled();
    const pdf = screen.getByRole("button", { name: d.downloadPdf });
    expect(pdf).toBeDisabled();
    expect(pdf).toHaveAccessibleDescription(d.pdfNotReady);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("enables both buttons when ready and requests the right format", async () => {
    let format: string | null = null;
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/download/`, ({ request }) => {
        format = new URL(request.url).searchParams.get("format");
        return new HttpResponse("x", {
          headers: { "Content-Disposition": 'attachment; filename="a.pdf"' },
        });
      }),
    );
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:x");
    vi.spyOn(URL, "revokeObjectURL").mockReturnValue(undefined);
    renderDocuments(<DownloadButtons version={aVersion()} />);
    await userEvent.click(screen.getByRole("button", { name: d.downloadPdf }));
    await waitFor(() => expect(format).toBe("pdf"));
  });

  it("shows a clear French message on a 409 integrity error, not the raw detail", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/document-versions/${VERSION_ID}/download/`, () =>
        HttpResponse.json({ detail: "IntegriteError: sha mismatch", errors: {} }, { status: 409 }),
      ),
    );
    renderDocuments(<DownloadButtons version={aVersion()} />);
    await userEvent.click(screen.getByRole("button", { name: d.downloadWord }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(d.integrityError);
    expect(alert).not.toHaveTextContent("sha mismatch");
  });

  it("shows the retry button only when the server allows it", async () => {
    let called = false;
    server.use(
      http.post(`${API_URL}/api/v1/document-versions/${VERSION_ID}/retry-pdf/`, () => {
        called = true;
        return HttpResponse.json(aVersion({ statut_pdf: "EN_COURS" }), { status: 202 });
      }),
    );
    renderDocuments(
      <DownloadButtons version={aVersion({ statut_pdf: "ECHEC", peut_relancer_pdf: true })} />,
    );
    await userEvent.click(screen.getByRole("button", { name: d.retryPdf }));
    await screen.findByRole("button", { name: d.retryPdf });
    expect(called).toBe(true);
  });

  it("hides the retry button when the server does not allow it", () => {
    renderDocuments(
      <DownloadButtons version={aVersion({ statut_pdf: "ECHEC", peut_relancer_pdf: false })} />,
    );
    expect(screen.queryByRole("button", { name: d.retryPdf })).not.toBeInTheDocument();
  });
});
