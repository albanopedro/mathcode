import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fixtures, jsonResponse } from "../test/fixtures";
import { Calculator } from "./Calculator";

// The real MathLive needs a browser that draws; this field keeps the LaTeX it is given.
vi.mock("mathlive", () => {
  class FakeField extends HTMLElement {
    latex = "";
    mathVirtualKeyboardPolicy = "";
    getValue() {
      return this.latex;
    }
    setValue(value: string) {
      this.latex = value;
    }
  }
  if (!customElements.get("math-field")) {
    customElements.define("math-field", FakeField);
  }
  return { MathfieldElement: FakeField };
});

function type(field: Element, latex: string) {
  (field as unknown as { latex: string }).latex = latex;
  field.dispatchEvent(new Event("input"));
}

describe("visual editor", () => {
  it("shows what will be calculated, and sends that text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(fixtures.arithmetic))),
    );
    const user = userEvent.setup();
    render(<Calculator />);
    await user.click(screen.getByRole("button", { name: "Editor visual" }));
    const field = await screen.findByLabelText("Expressão ou equação (editor visual)");

    type(field, "\\frac{1}{2}+\\sqrt{2}");
    expect(await screen.findByText("(1)/(2)+sqrt(2)")).toBeInTheDocument();

    field.dispatchEvent(new Event("change")); // Enter in the editor
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body.input).toBe("(1)/(2)+sqrt(2)");
    expect(localStorage.getItem("mathcode.editor.v1")).toBe("visual");
  });

  it("starts from the text already typed, and goes back to the text field", async () => {
    const user = userEvent.setup();
    render(<Calculator />);
    await user.type(screen.getByLabelText("Expressão ou equação"), "x^2");
    await user.click(screen.getByRole("button", { name: "Editor visual" }));
    const field = await screen.findByLabelText("Expressão ou equação (editor visual)");
    expect((field as unknown as { latex: string }).latex).toBe("x^2");

    await user.click(screen.getByRole("button", { name: "Editor visual" }));
    expect(screen.getByLabelText("Expressão ou equação")).toHaveValue("x^2");
    expect(localStorage.getItem("mathcode.editor.v1")).toBeNull();
  });
});
