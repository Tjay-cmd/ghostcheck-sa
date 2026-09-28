import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://ghostcheck-sa.invalid",
  trailingSlash: "always",
  build: { format: "directory" },
});
