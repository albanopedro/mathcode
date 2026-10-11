/** Whether the result is calculated while typing, remembered in this browser (ADR 0023). */
export const LIVE_KEY = "mathcode.live.v1";

/** On unless the user turned it off. */
export function loadLive(): boolean {
  try {
    return window.localStorage.getItem(LIVE_KEY) !== "off";
  } catch {
    return true;
  }
}

export function saveLive(live: boolean): void {
  try {
    if (live) {
      window.localStorage.removeItem(LIVE_KEY);
    } else {
      window.localStorage.setItem(LIVE_KEY, "off");
    }
  } catch {
    // Blocked storage: the choice lasts until the page is closed.
  }
}

/** How long the typing must pause before a live calculation starts. */
export const LIVE_DELAY_MS = 600;
