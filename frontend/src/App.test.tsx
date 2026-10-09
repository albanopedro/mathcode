import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App: theme and keyboard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.classList.remove("dark");
  });

  it("switches the theme and remembers it", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // the API status stays pending
    const user = userEvent.setup();
    render(<App />);
    const group = screen.getByRole("group", { name: "Tema" });
    expect(screen.getByRole("button", { name: "Sistema" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Escuro" }));
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("mathcode.theme.v1")).toBe("dark");
    await user.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement).not.toHaveClass("dark");
    expect(group).toBeInTheDocument();
  });

  it("starts with a link that skips to the result", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const user = userEvent.setup();
    render(<App />);
    await user.tab();
    const link = screen.getByRole("link", { name: "Pular para o resultado" });
    expect(link).toHaveFocus();
    expect(link).toHaveAttribute("href", "#result-area");
    expect(document.getElementById("result-area")).toHaveAttribute("tabindex", "-1");
  });
});
