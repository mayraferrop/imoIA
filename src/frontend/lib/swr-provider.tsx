"use client";

import { SWRConfig } from "swr";
import { fetcher } from "./api";

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: false,
        revalidateOnReconnect: true,
        revalidateIfStale: false,
        dedupingInterval: 300_000,
        keepPreviousData: true,
        shouldRetryOnError: false,
      }}
    >
      {children}
    </SWRConfig>
  );
}
