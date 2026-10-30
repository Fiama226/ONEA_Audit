import { Fragment, type ReactNode } from "react";

const START = "\u0002";
const END = "\u0003";

/**
 * Découpe un extrait de recherche : le texte entre `\u0002` et `\u0003` devient un `<mark>`.
 * Tout le reste (y compris du HTML) reste du texte : React l'échappe. Jamais de HTML injecté.
 */
export function Highlight({ text }: { text: string }) {
  const nodes: ReactNode[] = [];
  let marked = false;
  let buffer = "";
  const flush = () => {
    if (buffer !== "") {
      nodes.push(
        marked ? (
          <mark key={nodes.length}>{buffer}</mark>
        ) : (
          <Fragment key={nodes.length}>{buffer}</Fragment>
        ),
      );
    }
    buffer = "";
  };
  for (const char of text) {
    if (char === START) {
      flush();
      marked = true;
    } else if (char === END) {
      flush();
      marked = false;
    } else {
      buffer += char;
    }
  }
  flush();
  return <>{nodes}</>;
}
