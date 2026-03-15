import React from "react";
import { Analytics } from "@vercel/analytics/react";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";

export default function Root({ children }) {
  const { siteConfig } = useDocusaurusContext();
  const enableVercelAnalytics = Boolean(siteConfig.customFields?.enableVercelAnalytics);

  return (
    <>
      {children}
      {enableVercelAnalytics ? <Analytics /> : null}
    </>
  );
}
