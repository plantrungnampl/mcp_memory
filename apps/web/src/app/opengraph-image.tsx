import { createSeoImage } from "@/lib/seo-image";

export const alt = "VibeRecall long-term memory for coding agents";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OpenGraphImage() {
  return createSeoImage(size);
}
