import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { loadEnvFile } from "node:process";
import type { NextConfig } from "next";

const dashboardDir = process.cwd();
const repoDir = resolve(dashboardDir, "..");

for (const envFile of [
  resolve(dashboardDir, ".env.local"),
  resolve(dashboardDir, ".env"),
  resolve(repoDir, ".env"),
]) {
  if (existsSync(envFile)) loadEnvFile(envFile);
}

const nextConfig: NextConfig = { agentRules: false };

export default nextConfig;
