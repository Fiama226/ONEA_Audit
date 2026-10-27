import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";

export function CallbackPage() {
  const { completeLogin } = useAuth();
  const navigate = useNavigate();
  // Le code d'autorisation n'est utilisable qu'une fois (StrictMode monte deux fois).
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void completeLogin().then((returnTo) => {
      void navigate(returnTo ?? "/erreur", { replace: true });
    });
  }, [completeLogin, navigate]);

  return (
    <p role="status" className="p-6 text-muted-foreground">
      {fr.common.loading}
    </p>
  );
}
