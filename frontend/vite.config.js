import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "inventory-root-fallback",
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          if (request.url === "/") request.url = "/index.html";
          next();
        });
      }
    }
  ]
});
