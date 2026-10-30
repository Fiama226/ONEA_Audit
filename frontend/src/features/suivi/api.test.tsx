import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { dashboardKeys } from "@/features/dashboard/keys";
import { notificationKeys } from "@/features/notifications/keys";
import { unreadRefetchInterval, useUnreadCount } from "@/features/notifications/api";
import { useSearch } from "@/features/recherche/api";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import {
  downloadFollowUpExport,
  downloadImplementationEvidence,
  useActionTransition,
  useDecideExtension,
  useUploadImplementationEvidence,
} from "./api";
import { actionSuivieFixture, PREUVE_ID, SUIVI_ID, preuveFixture } from "./fixtures";
import { suiviKeys } from "./keys";
import { suiviQuery } from "./query";

const download = vi.hoisted(() => vi.fn());
const upload = vi.hoisted(() => vi.fn());
vi.mock("@/lib/download", () => ({ downloadBlob: download }));
vi.mock("@/api/upload", () => ({ uploadWithProgress: upload }));

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, invalidate, wrapper };
}

beforeEach(() => {
  download.mockReset();
  upload.mockReset();
});

describe("suiviQuery", () => {
  it("répète les listes, sérialise les booléens et omet les vides", () => {
    expect(
      suiviQuery({ statut: ["A_LANCER", "EN_COURS"], en_retard: true, mission: "", annee: 2026 }),
    ).toBe("?statut=A_LANCER&statut=EN_COURS&en_retard=true&annee=2026");
    expect(suiviQuery({ statut: [], mine: undefined })).toBe("");
  });
});

describe("useActionTransition", () => {
  it.each([
    ["start", undefined, {}],
    ["declare-done", "Terminé", { commentaire: "Terminé" }],
    ["propose-abandon", "Obsolète", { justification: "Obsolète" }],
    ["verify", undefined, {}],
    ["reject", "Preuve illisible", { motif: "Preuve illisible" }],
    ["close", undefined, {}],
    ["accept-abandon", "Accepté", { commentaire: "Accepté" }],
    ["reopen", "Reprise", { motif: "Reprise" }],
    ["comment", "Point", { texte: "Point" }],
  ] as const)("envoie %s sur la bonne route avec le bon corps", async (kind, text, body) => {
    let received: { url: string; body: unknown } | undefined;
    server.use(
      http.post(`${API_URL}/api/v1/follow-up/actions/${SUIVI_ID}/${kind}/`, async ({ request }) => {
        received = { url: request.url, body: await request.json() };
        return HttpResponse.json(actionSuivieFixture);
      }),
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useActionTransition(), { wrapper });
    await act(() => result.current.mutateAsync({ id: SUIVI_ID, kind, text }));
    expect(received?.body).toEqual(body);
  });

  it("invalide l'action, les listes, les tableaux de bord et le compteur de notifications", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/follow-up/actions/${SUIVI_ID}/start/`, () =>
        HttpResponse.json(actionSuivieFixture),
      ),
    );
    const { wrapper, invalidate } = setup();
    const { result } = renderHook(() => useActionTransition(), { wrapper });
    await act(() => result.current.mutateAsync({ id: SUIVI_ID, kind: "start" }));
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(suiviKeys.action(SUIVI_ID));
    expect(keys).toContainEqual(suiviKeys.all);
    expect(keys).toContainEqual(dashboardKeys.all);
    expect(keys).toContainEqual(notificationKeys.unread);
  });

  it("n'invalide rien quand le serveur refuse", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/follow-up/actions/${SUIVI_ID}/verify/`, () =>
        HttpResponse.json({ detail: "Interdit" }, { status: 403 }),
      ),
    );
    const { wrapper, invalidate } = setup();
    const { result } = renderHook(() => useActionTransition(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: SUIVI_ID, kind: "verify" }).catch(() => undefined);
    });
    expect(invalidate).not.toHaveBeenCalled();
  });
});

describe("useDecideExtension", () => {
  it("accepte ou refuse avec un commentaire", async () => {
    let url = "";
    server.use(
      http.post(
        `${API_URL}/api/v1/follow-up/extension-requests/r1/refuse/`,
        async ({ request }) => {
          url = request.url;
          expect(await request.json()).toEqual({ commentaire: "Délai excessif" });
          return HttpResponse.json({});
        },
      ),
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useDecideExtension(), { wrapper });
    await act(() =>
      result.current.mutateAsync({ id: "r1", decision: "refuse", commentaire: "Délai excessif" }),
    );
    expect(url).toContain("/extension-requests/r1/refuse/");
  });
});

describe("useUploadImplementationEvidence", () => {
  it("envoie le fichier en multipart avec progression et invalide les preuves", async () => {
    upload.mockResolvedValue(preuveFixture);
    const { wrapper, invalidate } = setup();
    const onProgress = vi.fn();
    const { result } = renderHook(() => useUploadImplementationEvidence(), { wrapper });
    const file = new File(["x"], "rapprochement.pdf", { type: "application/pdf" });
    await act(() =>
      result.current.mutateAsync({ actionId: SUIVI_ID, file, libelle: "Octobre", onProgress }),
    );
    const [url, form, progress] = upload.mock.calls[0] as [string, FormData, unknown];
    expect(url).toBe(`/api/v1/follow-up/evidence/?action=${SUIVI_ID}`);
    expect(form.get("action")).toBe(SUIVI_ID);
    expect(form.get("libelle")).toBe("Octobre");
    expect(form.get("fichier")).toBeInstanceOf(File);
    expect(progress).toBe(onProgress);
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(suiviKeys.evidence(SUIVI_ID));
  });
});

describe("téléchargements", () => {
  it("transforme un 409 sur une preuve en message d'altération", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/follow-up/evidence/${PREUVE_ID}/download/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 409 }),
      ),
    );
    await expect(downloadImplementationEvidence(PREUVE_ID, "p.pdf")).rejects.toThrow(
      fr.suivi.evidenceAltered,
    );
    expect(download).not.toHaveBeenCalled();
  });

  it("enregistre la preuve sous le nom demandé", async () => {
    server.use(
      http.get(
        `${API_URL}/api/v1/follow-up/evidence/${PREUVE_ID}/download/`,
        () => new HttpResponse("contenu"),
      ),
    );
    await downloadImplementationEvidence(PREUVE_ID, "preuve.pdf");
    expect(download).toHaveBeenCalledWith(expect.anything(), "preuve.pdf");
  });

  it("exporte avec les filtres courants, sans pagination ni tri", async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${API_URL}/api/v1/follow-up/actions/export/`, ({ request }) => {
        url = new URL(request.url);
        return new HttpResponse("a;b", {
          headers: { "Content-Disposition": 'attachment; filename="actions.csv"' },
        });
      }),
    );
    await downloadFollowUpExport(
      "actions",
      { statut: ["A_LANCER", "EN_COURS"], en_retard: true, page: 2, ordering: "echeance" },
      "csv",
    );
    expect(url?.searchParams.getAll("statut")).toEqual(["A_LANCER", "EN_COURS"]);
    expect(url?.searchParams.get("en_retard")).toBe("true");
    expect(url?.searchParams.get("format")).toBe("csv");
    expect(url?.searchParams.has("page")).toBe(false);
    expect(url?.searchParams.has("ordering")).toBe(false);
    expect(download).toHaveBeenCalledWith(expect.anything(), "actions.csv");
  });
});

describe("useUnreadCount", () => {
  it("se rafraîchit toutes les 60 s et au retour sur l'onglet, sauf onglet caché", () => {
    server.use(
      http.get(`${API_URL}/api/v1/notifications/unread-count/`, () =>
        HttpResponse.json({ count: 3 }),
      ),
    );
    const { client, wrapper } = setup();
    const { result } = renderHook(() => useUnreadCount(), { wrapper });
    const query = client.getQueryCache().find({ queryKey: notificationKeys.unread });
    const options = query?.options as Record<string, unknown> | undefined;
    expect(options?.refetchOnWindowFocus).toBe(true);
    expect(options?.refetchInterval).toBe(unreadRefetchInterval);
    expect(unreadRefetchInterval()).toBe(60_000);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    expect(unreadRefetchInterval()).toBe(false);
    vi.restoreAllMocks();
    return waitFor(() => expect(result.current.data?.count).toBe(3));
  });
});

describe("useSearch", () => {
  it("n'interroge pas le serveur sous 2 caractères", () => {
    const { wrapper } = setup();
    const { result } = renderHook(() => useSearch(" a "), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it.each([
    [429, fr.suivi.searchRateLimited],
    [503, fr.suivi.searchUnavailable],
  ])("traduit le statut %i", async (status, message) => {
    server.use(
      http.get(`${API_URL}/api/v1/search/`, () =>
        HttpResponse.json({ detail: "brut" }, { status }),
      ),
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useSearch("achats", ["ACTION"]), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe(message);
  });

  it("transmet q et types", async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${API_URL}/api/v1/search/`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ resultats: [], plus: false });
      }),
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useSearch(" achats ", ["MISSION", "ACTION"]), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(url?.searchParams.get("q")).toBe("achats");
    expect(url?.searchParams.get("types")).toBe("MISSION,ACTION");
  });
});
