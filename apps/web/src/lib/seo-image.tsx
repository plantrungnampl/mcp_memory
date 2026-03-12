import { ImageResponse } from "next/og";

import { BRAND_NAME, MARKETING_DESCRIPTION } from "@/lib/seo";

type SeoImageOptions = {
  width: number;
  height: number;
};

export function createSeoImage({ width, height }: SeoImageOptions) {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          height: "100%",
          width: "100%",
          background:
            "radial-gradient(circle at top left, rgba(168,85,247,0.45), rgba(17,17,19,0) 38%), linear-gradient(135deg, #080810 0%, #0f172a 100%)",
          color: "#f8fafc",
          fontFamily: "Arial, sans-serif",
          padding: "72px",
        }}
      >
        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "column",
            justifyContent: "space-between",
            border: "1px solid rgba(148, 163, 184, 0.18)",
            borderRadius: "32px",
            background: "rgba(15, 23, 42, 0.72)",
            padding: "56px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              fontSize: "28px",
              letterSpacing: "0.24em",
              textTransform: "uppercase",
              color: "#c084fc",
            }}
          >
            <div
              style={{
                display: "flex",
                height: "48px",
                width: "48px",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "14px",
                background: "linear-gradient(135deg, #7a2dbe 0%, #a855f7 100%)",
                color: "#ffffff",
                fontSize: "24px",
                fontWeight: 700,
                letterSpacing: "0.08em",
              }}
            >
              VR
            </div>
            {BRAND_NAME}
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "24px",
              maxWidth: "900px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                color: "#22c55e",
                fontSize: "24px",
                textTransform: "uppercase",
                letterSpacing: "0.16em",
              }}
            >
              <div
                style={{
                  height: "10px",
                  width: "10px",
                  borderRadius: "9999px",
                  backgroundColor: "#22c55e",
                }}
              />
              Native MCP memory platform
            </div>
            <div
              style={{
                display: "flex",
                fontSize: "72px",
                lineHeight: 1.02,
                fontWeight: 700,
              }}
            >
              Long-term memory for coding agents
            </div>
            <div
              style={{
                display: "flex",
                maxWidth: "860px",
                color: "#cbd5e1",
                fontSize: "30px",
                lineHeight: 1.4,
              }}
            >
              {MARKETING_DESCRIPTION}
            </div>
          </div>
        </div>
      </div>
    ),
    {
      width,
      height,
    },
  );
}
