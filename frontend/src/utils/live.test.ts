import { describe, expect, it } from "vitest";

import { LIVE_KEY, loadLive, saveLive } from "./live";

describe("live preference", () => {
  it("is on by default and remembers being turned off", () => {
    expect(loadLive()).toBe(true);
    saveLive(false);
    expect(localStorage.getItem(LIVE_KEY)).toBe("off");
    expect(loadLive()).toBe(false);
    saveLive(true);
    expect(loadLive()).toBe(true);
  });

  it("never throws when the storage is blocked", () => {
    const blocked = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });
    try {
      expect(loadLive()).toBe(true);
      expect(() => saveLive(false)).not.toThrow();
    } finally {
      Object.defineProperty(window, "localStorage", blocked!);
    }
  });
});
