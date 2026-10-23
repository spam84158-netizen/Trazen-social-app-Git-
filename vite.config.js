import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const backend = process.env.VITE_API_PROXY || "http://ambassador.seyori.name.ng:2059";
export default defineConfig({ plugins: [react()], server: { proxy: { "/api": { target: backend, changeOrigin: true }, "/healthz": { target: backend, changeOrigin: true } } } });
