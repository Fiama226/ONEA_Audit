import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { createQueryClient } from "./api/queryClient";
import { AuthProvider } from "./auth/AuthProvider";
import { createAppRouter } from "./routes";
import "./styles/globals.css";

const container = document.getElementById("root");
if (!container) throw new Error("Élément racine introuvable");

const queryClient = createQueryClient();
const router = createAppRouter();

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
