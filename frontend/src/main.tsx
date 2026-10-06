import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// KaTeX styles and fonts are bundled by Vite: no CDN, works offline (ADR 0001).
import "katex/dist/katex.min.css";

import App from "./App";
import "./index.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Elemento #root não encontrado em index.html");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
