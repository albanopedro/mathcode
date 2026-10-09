/** Whether the visual editor (MathLive) is on, remembered in this browser (ADR 0020). */
export const EDITOR_KEY = "mathcode.editor.v1";

export function loadEditor(): boolean {
  try {
    return window.localStorage.getItem(EDITOR_KEY) === "visual";
  } catch {
    return false;
  }
}

export function saveEditor(visual: boolean): void {
  try {
    if (visual) {
      window.localStorage.setItem(EDITOR_KEY, "visual");
    } else {
      window.localStorage.removeItem(EDITOR_KEY);
    }
  } catch {
    // Blocked storage: the choice lasts until the page is closed.
  }
}
