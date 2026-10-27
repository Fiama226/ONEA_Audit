import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Breadcrumb, BreadcrumbEllipsis } from "./breadcrumb";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "./dialog";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "./sheet";

describe("shadcn components speak French", () => {
  it("Dialog close controls are named Fermer", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Titre</DialogTitle>
          <DialogDescription>Description</DialogDescription>
          <DialogFooter showCloseButton />
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getAllByRole("button", { name: "Fermer" })).toHaveLength(2);
    expect(screen.queryByText("Close")).not.toBeInTheDocument();
  });

  it("Sheet close control is named Fermer", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetTitle>Titre</SheetTitle>
          <SheetDescription>Description</SheetDescription>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByRole("button", { name: "Fermer" })).toBeInTheDocument();
  });

  it("Breadcrumb is labelled and ellipsis is named in French", () => {
    render(
      <Breadcrumb>
        <BreadcrumbEllipsis />
      </Breadcrumb>,
    );
    expect(screen.getByRole("navigation", { name: "Fil d'Ariane" })).toBeInTheDocument();
    expect(screen.getByText("Plus")).toBeInTheDocument();
  });
});
