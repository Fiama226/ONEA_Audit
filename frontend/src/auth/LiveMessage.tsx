import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type Props = {
  /** Texte à annoncer ; null : la zone reste vide (mais présente). */
  message: string | null;
  role: "alert" | "status";
  className?: string;
};

/**
 * Zone d'annonce rendue d'abord vide, puis remplie : un lecteur d'écran n'annonce de façon
 * fiable que le texte inséré dans une zone live déjà présente (pas une zone apparue avec
 * son contenu au chargement de la page).
 */
export function LiveMessage({ message, role, className }: Props) {
  const [shown, setShown] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setShown(message), 0);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <div role={role} className={cn(shown ? className : "sr-only")}>
      {shown}
    </div>
  );
}
