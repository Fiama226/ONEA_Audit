const clean = (value: string | null | undefined): string => (value ?? "").normalize("NFC").trim();

/** Initiales d'affichage (prénom + nom), repli sur l'identifiant, puis « ? ». Ne lève jamais. */
export function initialsOf(
  first: string | null | undefined,
  last: string | null | undefined,
  username: string | null | undefined,
): string {
  const letters = [...clean(first)]
    .slice(0, 1)
    .concat([...clean(last)].slice(0, 1))
    .join("");
  const text = letters || [...clean(username)].slice(0, 2).join("");
  return (text || "?").toLocaleUpperCase("fr-FR");
}
