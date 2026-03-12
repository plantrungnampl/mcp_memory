import type { Metadata } from "next";

import { Providers } from "@/components/providers";
import {
  BRAND_NAME,
  CONTROL_PLANE_DESCRIPTION,
  getMetadataBase,
} from "@/lib/seo";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: getMetadataBase(),
  title: {
    default: BRAND_NAME,
    template: `%s | ${BRAND_NAME}`,
  },
  description: CONTROL_PLANE_DESCRIPTION,
  applicationName: BRAND_NAME,
  referrer: "origin-when-cross-origin",
  creator: BRAND_NAME,
  publisher: BRAND_NAME,
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
