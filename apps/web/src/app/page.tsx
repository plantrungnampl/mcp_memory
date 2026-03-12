import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";
import { faqItems } from "@/components/landing/landing-data";
import {
  BRAND_NAME,
  GITHUB_REPO_URL,
  MARKETING_DESCRIPTION,
  MARKETING_KEYWORDS,
  MARKETING_PAGE_TITLE,
  getAppUrl,
  sanitizeJsonLd,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: {
    absolute: MARKETING_PAGE_TITLE,
  },
  description: MARKETING_DESCRIPTION,
  keywords: [...MARKETING_KEYWORDS],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: MARKETING_PAGE_TITLE,
    description: MARKETING_DESCRIPTION,
    url: getAppUrl("/"),
    siteName: BRAND_NAME,
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: MARKETING_PAGE_TITLE,
    description: MARKETING_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      noimageindex: false,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  category: "technology",
};

export default function HomePage() {
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: BRAND_NAME,
      url: getAppUrl("/"),
      logo: getAppUrl("/favicon.ico"),
      sameAs: [GITHUB_REPO_URL],
    },
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      name: BRAND_NAME,
      applicationCategory: "DeveloperApplication",
      operatingSystem: "macOS, Windows, Linux",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      description: MARKETING_DESCRIPTION,
      url: getAppUrl("/"),
    },
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: faqItems.map((item) => ({
        "@type": "Question",
        name: item.question,
        acceptedAnswer: {
          "@type": "Answer",
          text: item.answer,
        },
      })),
    },
  ];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: sanitizeJsonLd(jsonLd),
        }}
      />
      <LandingPage />
    </>
  );
}
