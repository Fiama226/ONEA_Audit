import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { BarList } from "./BarList";

const data = [
  { key: "a", label: "Alpha", value: 8 },
  { key: "b", label: "Bravo", value: 2, href: "/b" },
];

describe("BarList", () => {
  it("shows values as text", () => {
    render(<BarList data={data} ariaLabel="Par direction" />, { wrapper: MemoryRouter });
    expect(screen.getByRole("list", { name: "Par direction" })).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  it("shows a tooltip on keyboard focus and hides it on blur", async () => {
    render(<BarList data={data} ariaLabel="Par direction" format={(n) => `${n} u.`} />, {
      wrapper: MemoryRouter,
    });
    expect(screen.queryByRole("tooltip")).toBeNull();
    await userEvent.tab();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Alpha : 8 u.");
    await userEvent.tab();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Bravo : 2 u.");
    await userEvent.tab();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("renders a link when href is given", () => {
    render(<BarList data={data} ariaLabel="Par direction" />, { wrapper: MemoryRouter });
    expect(screen.getByRole("link", { name: /Bravo/ })).toHaveAttribute("href", "/b");
  });

  it("has no axe violation", async () => {
    const { container } = render(<BarList data={data} ariaLabel="Par direction" />, {
      wrapper: MemoryRouter,
    });
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
