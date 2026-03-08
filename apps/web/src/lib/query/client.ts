import { QueryClient } from "@tanstack/react-query";

import { ControlPlaneQueryError } from "@/lib/query/fetch";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry(failureCount, error) {
          if (error instanceof ControlPlaneQueryError && error.status < 500) {
            return false;
          }
          return failureCount < 1;
        },
      },
    },
  });
}
