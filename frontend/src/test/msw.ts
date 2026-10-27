import { setupServer } from "msw/node";

export const API_URL = "http://localhost:8000";

/** Serveur MSW partagé par les tests ; les handlers sont ajoutés par test via server.use(). */
export const server = setupServer();
