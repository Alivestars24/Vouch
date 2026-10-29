// Trusted synthetic input only; untrusted user media is decoded exclusively in the sandbox.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const directory = fileURLToPath(new URL("../../.local/fixtures/", import.meta.url));
const destination = fileURLToPath(new URL("../../.local/fixtures/decoded-blue-2s.mp4", import.meta.url));
mkdirSync(directory, { recursive: true });
execFileSync("ffmpeg", [
  "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=25",
  "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", destination,
], { stdio: "pipe", timeout: 20_000, windowsHide: true });
process.stdout.write("Synthetic two-second blue video generated in ignored .local/fixtures/.\n");
