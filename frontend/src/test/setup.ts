import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { loadKatex } from "../utils/katex";

// KaTeX is loaded on demand in the app; in the tests it is ready from the start, so
// formulas render as soon as their component does.
await loadKatex();

afterEach(() => {
  cleanup();
  // The history lives in localStorage: each test starts without one.
  localStorage.clear();
});
