import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Highlight } from "./highlight";

describe("Highlight", () => {
  it("transforme les repères en <mark>", () => {
    const { container } = render(<Highlight text={"a\u0002b\u0003c"} />);
    expect(container.innerHTML).toBe("a<mark>b</mark>c");
  });

  it("garde du HTML comme texte, sans élément injecté", () => {
    const hostile = "<img src=x onerror=alert(1)> \u0002<script>x</script>\u0003";
    const { container } = render(<Highlight text={hostile} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("mark")?.textContent).toBe("<script>x</script>");
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("tolère des repères déséquilibrés et un texte vide", () => {
    expect(render(<Highlight text={"\u0003seul\u0003"} />).container.innerHTML).toBe("seul");
    expect(render(<Highlight text={"a\u0002b"} />).container.innerHTML).toBe("a<mark>b</mark>");
    expect(render(<Highlight text="" />).container.innerHTML).toBe("");
  });
});
