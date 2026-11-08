import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The UI is a thin client of the operation registry (plan D2, 04 D13). In M0 it only renders a
// placeholder; the vertical slice (step 3) adds the generated TypeScript client.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", strictPort: false },
});
