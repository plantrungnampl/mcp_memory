import assert from "node:assert/strict";
import test from "node:test";

import { PROJECT_STORAGE_KEY } from "@/components/projects/project-selection";
import {
  readStoredProjectId,
  subscribeToStoredProjectId,
  writeStoredProjectId,
} from "@/components/projects/project-storage";

type FakeWindow = EventTarget & {
  localStorage: {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
  };
};

function installFakeWindow() {
  const originalWindow = globalThis.window;
  const target = new EventTarget();
  const values = new Map<string, string>();
  const fakeWindow = Object.assign(target, {
    localStorage: {
      getItem(key: string): string | null {
        return values.get(key) ?? null;
      },
      setItem(key: string, value: string): void {
        values.set(key, value);
      },
    },
  }) as FakeWindow;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: fakeWindow,
  });

  return {
    fakeWindow,
    restore() {
      Object.defineProperty(globalThis, "window", {
        configurable: true,
        value: originalWindow,
      });
    },
  };
}

test("readStoredProjectId returns null without a browser window", () => {
  const originalWindow = globalThis.window;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: undefined,
  });

  try {
    assert.equal(readStoredProjectId(), null);
  } finally {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});

test("writeStoredProjectId persists the project id and notifies subscribers", () => {
  const { restore } = installFakeWindow();
  let notifications = 0;
  const unsubscribe = subscribeToStoredProjectId(() => {
    notifications += 1;
  });

  try {
    writeStoredProjectId("proj_store");

    assert.equal(window.localStorage.getItem(PROJECT_STORAGE_KEY), "proj_store");
    assert.equal(readStoredProjectId(), "proj_store");
    assert.equal(notifications, 1);
  } finally {
    unsubscribe();
    restore();
  }
});
