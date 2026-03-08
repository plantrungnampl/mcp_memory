import { spawn } from "node:child_process";
import { lstat, mkdir, readlink, rm, symlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.resolve(scriptDir, "..");
const rootDir = path.resolve(appDir, "..", "..");
const rootNodeModulesDir = path.join(rootDir, "node_modules");
const rootNextLink = path.join(rootNodeModulesDir, "next");
const appNextTarget = path.join(appDir, "node_modules", "next");
const eslintBin = path.join(appDir, "node_modules", "eslint", "bin", "eslint.js");

async function ensureRootNextSymlink() {
  const relativeTarget = path.relative(rootNodeModulesDir, appNextTarget);
  await mkdir(rootNodeModulesDir, { recursive: true });

  try {
    const stat = await lstat(rootNextLink);
    if (stat.isSymbolicLink()) {
      const currentTarget = await readlink(rootNextLink);
      if (currentTarget === relativeTarget) {
        return;
      }
    }
    await rm(rootNextLink, { force: true, recursive: true });
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      // Link does not exist yet.
    } else {
      throw error;
    }
  }

  await symlink(relativeTarget, rootNextLink, "dir");
}

await ensureRootNextSymlink();

const child = spawn(process.execPath, [eslintBin, "."], {
  cwd: appDir,
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
