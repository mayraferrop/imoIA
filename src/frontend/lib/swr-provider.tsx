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
        // Retry com backoff cobre race condition: primeiro fetch pode
        // disparar antes da sessao auth hidratar (getSession é async).
        // 3 tentativas em ~6s dao margem folgada para auth estabilizar.
        shouldRetryOnError: true,
        errorRetryCount: 3,
        errorRetryInterval: 1500,
      }}
    >
      {children}
    </SWRConfig>
  );
}
