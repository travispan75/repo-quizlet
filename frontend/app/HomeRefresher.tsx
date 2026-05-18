"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomeRefresher({ enabled }: { enabled: boolean }) {
  const router = useRouter();
  useEffect(() => {
    if (!enabled) return;
    const interval = setInterval(() => router.refresh(), 3000);
    return () => clearInterval(interval);
  }, [enabled, router]);
  return null;
}
