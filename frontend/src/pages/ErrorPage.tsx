import { Navigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fr } from "@/i18n/fr";

export function ErrorPage() {
  const { status, retry } = useAuth();
  // Sur /erreur, une fois la reprise réussie on retourne à l'application.
  if (status === "authenticated" || status === "anonymous") return <Navigate to="/" replace />;

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{fr.errors.unreachableTitle}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p role="alert">{fr.errors.unreachable}</p>
          <Button onClick={() => void retry()}>{fr.common.retry}</Button>
        </CardContent>
      </Card>
    </main>
  );
}
