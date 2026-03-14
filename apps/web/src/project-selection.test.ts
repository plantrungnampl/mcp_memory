import assert from "node:assert/strict";
import test from "node:test";

import type { ProjectSummary } from "@/lib/api/types";

import {
  extractPathProjectId,
  resolveProjectNavigationState,
  resolveSelectedProjectId,
} from "@/components/projects/project-selection";

const PROJECTS: ProjectSummary[] = [
  {
    id: "proj_test",
    name: "test",
    plan: "free",
    createdAt: "2026-03-14T00:00:00.000Z",
  },
  {
    id: "proj_nam",
    name: "nam",
    plan: "free",
    createdAt: "2026-03-13T00:00:00.000Z",
  },
];

test("extractPathProjectId returns the route project id for workspace paths", () => {
  assert.equal(extractPathProjectId("/projects/proj_nam/tokens"), "proj_nam");
  assert.equal(extractPathProjectId("/projects"), null);
});

test("resolveSelectedProjectId uses the query project on the directory route", () => {
  const selected = resolveSelectedProjectId({
    pathname: "/projects",
    searchParams: new URLSearchParams("project=proj_nam"),
    projects: PROJECTS,
  });

  assert.equal(selected, "proj_nam");
});

test("resolveProjectNavigationState preserves a valid stored project on /projects without query", () => {
  const state = resolveProjectNavigationState({
    pathname: "/projects",
    queryProjectId: null,
    activeProjectId: null,
    storedProjectId: "proj_nam",
    projects: PROJECTS,
  });

  assert.equal(state.selectedProjectId, null);
  assert.equal(state.resolvedProjectId, "proj_nam");
  assert.equal(state.shouldHydrateDirectoryQuery, true);
});

test("resolveProjectNavigationState does not overwrite stored project with the first project on /projects", () => {
  const state = resolveProjectNavigationState({
    pathname: "/projects",
    queryProjectId: null,
    activeProjectId: null,
    storedProjectId: "proj_nam",
    projects: PROJECTS,
  });

  assert.notEqual(state.resolvedProjectId, PROJECTS[0]?.id ?? null);
});

test("resolveProjectNavigationState falls back to the first project only when no valid selection exists", () => {
  const state = resolveProjectNavigationState({
    pathname: "/projects",
    queryProjectId: null,
    activeProjectId: null,
    storedProjectId: "proj_missing",
    projects: PROJECTS,
  });

  assert.equal(state.shouldHydrateDirectoryQuery, false);
  assert.equal(state.resolvedProjectId, PROJECTS[0]?.id ?? null);
});

test("resolveProjectNavigationState prefers the route project for workspace pages", () => {
  const state = resolveProjectNavigationState({
    pathname: "/projects/proj_nam/tokens",
    queryProjectId: "proj_test",
    activeProjectId: "proj_test",
    storedProjectId: "proj_test",
    projects: PROJECTS,
  });

  assert.equal(state.selectedProjectId, "proj_nam");
  assert.equal(state.resolvedProjectId, "proj_nam");
  assert.equal(state.shouldHydrateDirectoryQuery, false);
});
