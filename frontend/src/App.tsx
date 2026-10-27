import { fr } from "@/i18n/fr";

export function App() {
  return (
    <main className="mx-auto max-w-[1280px] p-6">
      <h1 className="text-2xl font-semibold">{fr.app.name}</h1>
      <p className="text-muted-foreground">{fr.app.tagline}</p>
    </main>
  );
}
