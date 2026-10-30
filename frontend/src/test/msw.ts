import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const API_URL = "http://localhost:8000";

/**
 * Serveur MSW partagé par les tests ; les handlers sont ajoutés par test via server.use().
 * Seul handler par défaut : le compteur de la cloche, interrogé par l'en-tête dans tout test qui
 * monte le shell.
 */
export const server = setupServer(
  http.get(`${API_URL}/api/v1/notifications/unread-count/`, () => HttpResponse.json({ count: 0 })),
);
