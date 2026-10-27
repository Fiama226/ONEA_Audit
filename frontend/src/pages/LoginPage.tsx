import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fr } from "@/i18n/fr";

function fromOf(state: unknown): string {
  if (typeof state === "object" && state !== null && "from" in state) {
    const from = (state as { from: unknown }).from;
    if (typeof from === "string") return from;
  }
  return "/";
}

export function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const from = fromOf(location.state);

  if (status === "authenticated") return <Navigate to={from} replace />;
  if (status === "error") return <Navigate to="/erreur" replace />;

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{fr.app.name}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-muted-foreground">{fr.auth.loginPrompt}</p>
          <Button onClick={() => void login(from)} disabled={status === "loading"}>
            {fr.auth.login}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
