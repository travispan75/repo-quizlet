"use client";

import { useEffect, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import type { ReactNode } from "react";

export default function ResizableLayout({
  sidebar,
  viewer,
  right,
}: {
  sidebar: ReactNode;
  viewer: ReactNode;
  right: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div
      className="h-screen"
      style={{ visibility: mounted ? "visible" : "hidden" }}
    >
      <Group orientation="horizontal">
        <Panel defaultSize={15} minSize={10}>
          <div className="h-screen bg-surface">{sidebar}</div>
        </Panel>
        <Separator className="relative z-10 -ml-px w-px bg-border hover:bg-border-hover cursor-ew-resize before:content-[''] before:absolute before:inset-y-0 before:-left-1 before:-right-1" />
        <Panel defaultSize={40} minSize={15}>
          <div className="h-screen">{viewer}</div>
        </Panel>
        <Separator className="relative z-10 -ml-px w-px bg-border hover:bg-border-hover cursor-ew-resize before:content-[''] before:absolute before:inset-y-0 before:-left-1 before:-right-1" />
        <Panel defaultSize={45} minSize={10}>
          <div className="h-screen overflow-y-auto overflow-x-hidden">{right}</div>
        </Panel>
      </Group>
    </div>
  );
}
