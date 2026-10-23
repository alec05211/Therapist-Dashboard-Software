import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 3001, strictPort: true },
  build: {
    sourcemap: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: fileURLToPath(new URL("./index.html", import.meta.url)),
      output: {
        entryFileNames: "assets/auth0-login.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: (asset) =>
          asset.name?.endsWith(".css")
            ? "assets/auth0-login.css"
            : "assets/[name][extname]",
      },
    },
  },
});
