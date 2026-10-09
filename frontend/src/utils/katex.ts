import type Katex from "katex";

type KatexModule = typeof Katex;

/**
 * KaTeX is loaded on demand, in a chunk of its own: the first page (the form) does not
 * need it, and the main chunk stays small. Its styles and fonts are still bundled
 * locally (main.tsx): nothing comes from a CDN (ADR 0001).
 */
let loaded: KatexModule | null = null;
let loading: Promise<KatexModule> | null = null;

/** KaTeX, if it is already loaded; null until then. */
export function katexIfLoaded(): KatexModule | null {
  return loaded;
}

export function loadKatex(): Promise<KatexModule> {
  loading ??= import("katex").then((module) => {
    loaded = module.default;
    return loaded;
  });
  return loading;
}
