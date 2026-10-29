import type { ComponentProps } from "react";

export type HeadingLevel = 3 | 4 | 5;

type Props = ComponentProps<"h3"> & { level: HeadingLevel };

/** Titre dont le niveau suit le contexte : h3 sur une page, h4 dans une zone d'étape (déjà en h3). */
export function Heading({ level, ...props }: Props) {
  const Tag = `h${level}` as "h3" | "h4" | "h5";
  return <Tag {...props} />;
}
