import type { MetadataRoute } from "next";

import { getMarketingUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: getMarketingUrl("/"),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
