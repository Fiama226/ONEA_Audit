import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { NotificationBell } from "./NotificationBell";
import { NotificationsPage } from "../pages/NotificationsPage";
import { compteurFixture, notificationFixture, notificationsPageFixture } from "../fixtures";

const BASE = `${API_URL}/api/v1/notifications`;

function setup(count = 1) {
  const calls: string[] = [];
  server.use(
    http.get(`${BASE}/unread-count/`, () => HttpResponse.json({ count })),
    http.get(`${BASE}/`, () => HttpResponse.json(notificationsPageFixture)),
    http.post(`${BASE}/:id/read/`, ({ params }) => {
      calls.push(`read:${String(params.id)}`);
      return HttpResponse.json({ ...notificationFixture, lue: true });
    }),
    http.post(`${BASE}/read-all/`, () => {
      calls.push("read-all");
      return HttpResponse.json(compteurFixture);
    }),
  );
  const utils = renderRoutes(
    [
      { path: "/", element: <NotificationBell /> },
      { path: "/notifications", element: <NotificationsPage /> },
      { path: "/recommandations/actions/:id", element: <h1>Page action</h1> },
    ],
    "RAI",
  );
  return { calls, ...utils };
}

describe("NotificationBell", () => {
  it("annonce le compteur de notifications non lues", async () => {
    setup(3);
    expect(await screen.findByRole("button", { name: "Notifications, 3 non lues" })).toBeVisible();
  });

  it("affiche 9+ au-delà de neuf", async () => {
    setup(14);
    await screen.findByRole("button", { name: "Notifications, 14 non lues" });
    expect(screen.getByText("9+")).toBeInTheDocument();
  });

  it("un clic marque la notification comme lue puis navigue vers son lien", async () => {
    const { calls, router } = setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Notifications, 1 non lues/ }));
    await user.click(await screen.findByRole("menuitem", { name: /Action déclarée réalisée/ }));
    await waitFor(() => expect(router.state.location.pathname).toMatch(/recommandations\/actions/));
    expect(calls).toContain(`read:${notificationFixture.id}`);
  });

  it("« Tout marquer comme lu » appelle read-all", async () => {
    const { calls } = setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Notifications, 1 non lues/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Tout marquer comme lu" }));
    await waitFor(() => expect(calls).toContain("read-all"));
  });

  it("une erreur de chargement n'est pas rendue comme une liste vide", async () => {
    setup();
    server.use(http.get(`${BASE}/`, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Notifications, 1 non lues/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/n'ont pas pu être chargées/);
    expect(screen.queryByText("Aucune notification.")).not.toBeInTheDocument();
  });

  it("propose « Voir toutes les notifications » et se ferme avec Échap", async () => {
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Notifications, 1 non lues/ }));
    expect(
      await screen.findByRole("menuitem", { name: "Voir toutes les notifications" }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
  });

  it("la page des notifications est accessible", async () => {
    setup();
    const { container } = renderRoutes([{ path: "*", element: <NotificationsPage /> }], "RAI");
    await screen.findByText(notificationFixture.titre);
    expect((await axe(container)).violations).toEqual([]);
  });
});
