import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type DataTableColumn } from "./DataTable";

type Row = { id: string; code: string; libelle: string };
const columns: DataTableColumn<Row>[] = [
  { id: "code", accessorKey: "code", header: "Code" },
  { id: "libelle", accessorKey: "libelle", header: "Libellé", enableSorting: false },
];
const data: Row[] = [
  { id: "1", code: "A", libelle: "Alpha" },
  { id: "2", code: "B", libelle: "Bravo" },
];

function setup(over: Partial<Parameters<typeof DataTable<Row>>[0]> = {}) {
  const props = {
    caption: "Liste des directions",
    columns,
    data,
    total: 45,
    page: 1,
    pageSize: 20,
    onPageChange: vi.fn(),
    onOrderingChange: vi.fn(),
    isLoading: false,
    empty: <p>Rien ici</p>,
    ...over,
  };
  render(<DataTable<Row> {...props} />);
  return props;
}

describe("DataTable", () => {
  it("renders a captioned table with rows", () => {
    setup();
    const table = screen.getByRole("table", { name: "Liste des directions" });
    expect(within(table).getByText("Alpha")).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(3);
  });

  it("paginates on the server", async () => {
    const props = setup({ page: 2 });
    expect(screen.getByText("Page 2 sur 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Page suivante" }));
    expect(props.onPageChange).toHaveBeenCalledWith(3);
    await userEvent.click(screen.getByRole("button", { name: "Page précédente" }));
    expect(props.onPageChange).toHaveBeenCalledWith(1);
  });

  it("scrolls horizontally in a labelled, focusable region instead of clipping wide tables", () => {
    setup();
    const table = screen.getByRole("table");
    const region = table.parentElement as HTMLElement;
    expect(region).toHaveClass("overflow-x-auto");
    expect(region).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("region")).toBe(region);
    expect(table.querySelector("thead")).toHaveClass("sticky");
  });

  it("agrees singular and plural in the result count", () => {
    setup({ total: 1, data: [data[0]!] });
    expect(screen.getByText("1 résultat")).toBeInTheDocument();
  });

  it("disables previous on the first page", () => {
    setup({ page: 1 });
    expect(screen.getByRole("button", { name: "Page précédente" })).toBeDisabled();
  });

  it("shows the empty slot when there is no data and no loading", () => {
    setup({ data: [], total: 0 });
    expect(screen.getByText("Rien ici")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows skeletons while loading", () => {
    setup({ data: [], total: 0, isLoading: true });
    expect(screen.queryByText("Rien ici")).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Liste des directions" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("cycles server ordering on sortable headers", async () => {
    const props = setup({ ordering: "code" });
    const th = screen.getByRole("columnheader", { name: /Code/ });
    expect(th).toHaveAttribute("aria-sort", "ascending");
    await userEvent.click(within(th).getByRole("button"));
    expect(props.onOrderingChange).toHaveBeenCalledWith("-code");
    expect(
      within(screen.getByRole("columnheader", { name: "Libellé" })).queryByRole("button"),
    ).not.toBeInTheDocument();
  });
});
