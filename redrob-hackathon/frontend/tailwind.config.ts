import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        prism: {
          bg: "#070b16",
          panel: "#0f172a",
          line: "#243044",
          cyan: "#38bdf8",
          green: "#22c55e",
          yellow: "#facc15",
          red: "#f87171"
        }
      },
      borderRadius: {
        card: "8px"
      }
    }
  },
  plugins: [tailwindcssAnimate]
};

export default config;
