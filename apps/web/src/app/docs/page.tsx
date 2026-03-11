import { permanentRedirect } from "next/navigation";

import { publicEnv } from "@/lib/env";

export default function DocsPage(): never {
  permanentRedirect(publicEnv.docsUrl);
}
