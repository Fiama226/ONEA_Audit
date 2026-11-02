import { createContext, useContext } from "react";

export type TutorielContextValue = {
  /** Réinitialise l'état côté serveur puis relance la visite. */
  relancer(): void;
};

export const TutorielContext = createContext<TutorielContextValue>({ relancer: () => {} });

export const useTutoriel = () => useContext(TutorielContext);
