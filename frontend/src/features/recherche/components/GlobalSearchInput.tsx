import { Search } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";

/**
 * Champ de recherche de l'en-tête : aucune requête ici, « Entrée » ouvre `/recherche?q=`
 * (la page porte la requête). Sous 1024 px, simple bouton vers la page.
 */
export function GlobalSearchInput() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    navigate(q ? `/recherche?q=${encodeURIComponent(q)}` : "/recherche");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") setValue("");
  };

  return (
    <>
      <form
        role="search"
        onSubmit={submit}
        aria-label={fr.shell.searchLabel}
        className="relative hidden lg:block lg:w-60 xl:w-80"
      >
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <Input
          type="search"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label={fr.shell.searchLabel}
          placeholder={fr.shell.searchPlaceholder}
          autoComplete="off"
          className="h-9 rounded-md border-transparent bg-surface-subtle pl-9 placeholder:text-text-muted"
        />
      </form>
      <Button
        asChild
        variant="ghost"
        size="icon"
        className="bg-surface-subtle text-text-muted lg:hidden"
      >
        <Link to="/recherche" aria-label={fr.rechercheNotifications.searchOpenMobile}>
          <Search className="size-4" aria-hidden />
        </Link>
      </Button>
    </>
  );
}
