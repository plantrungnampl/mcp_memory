import type { MetadataRoute } from "next";

import { getAppUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: getAppUrl("/"),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
