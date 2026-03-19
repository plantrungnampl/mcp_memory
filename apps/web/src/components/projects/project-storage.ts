"use client";

import { useSyncExternalStore } from "react";

import { PROJECT_STORAGE_KEY } from "@/components/projects/project-selection";

const PROJECT_STORAGE_EVENT = "viberecall:project-storage";

function hasBrowserWindow(): boolean {
  return typeof window !== "undefined";
}

export function readStoredProjectId(): string | null {
  if (!hasBrowserWindow()) {
    return null;
  }

  return window.localStorage.getItem(PROJECT_STORAGE_KEY);
}

export function subscribeToStoredProjectId(callback: () => void): () => void {
  if (!hasBrowserWindow()) {
    return () => {};
  }

  const handleChange = () => {
    callback();
  };

  window.addEventListener("storage", handleChange);
  window.addEventListener(PROJECT_STORAGE_EVENT, handleChange);

  return () => {
    window.removeEventListener("storage", handleChange);
    window.removeEventListener(PROJECT_STORAGE_EVENT, handleChange);
  };
}

export function writeStoredProjectId(projectId: string): void {
  if (!hasBrowserWindow()) {
    return;
  }

  if (window.localStorage.getItem(PROJECT_STORAGE_KEY) === projectId) {
    return;
  }

  window.localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
  window.dispatchEvent(new Event(PROJECT_STORAGE_EVENT));
}

export function useStoredProjectId(): string | null {
  return useSyncExternalStore(subscribeToStoredProjectId, readStoredProjectId, () => null);
}
