import type { MetadataRoute } from "next";

import { getAppUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/auth/", "/projects", "/projects/"],
    },
    sitemap: getAppUrl("/sitemap.xml"),
  };
}
