import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  server: {
    port: 8001,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:81",
        changeOrigin: true,
      },
    },
  },
});
