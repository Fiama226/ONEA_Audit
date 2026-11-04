import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const API_URL = "http://localhost:8000";

/** Jeton CSRF servi par défaut par GET /api/v1/auth/csrf/. */
export const TEST_CSRF = "csrf-test";

/**
 * Serveur MSW partagé par les tests ; les handlers sont ajoutés par test via server.use().
 * Handlers par défaut : le compteur de la cloche (interrogé par l'en-tête dans tout test qui
 * monte le shell), le jeton CSRF (requis par toute écriture) et une session anonyme (401).
 */
export const server = setupServer(
  http.get(`${API_URL}/api/v1/notifications/unread-count/`, () => HttpResponse.json({ count: 0 })),
  http.get(`${API_URL}/api/v1/auth/csrf/`, () => HttpResponse.json({ csrf_token: TEST_CSRF })),
  http.get(`${API_URL}/api/v1/auth/session/`, () =>
    HttpResponse.json(
      { detail: "Informations d'authentification non fournies.", errors: {} },
      { status: 401 },
    ),
  ),
);
