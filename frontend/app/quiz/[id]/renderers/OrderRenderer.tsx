"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  restrictToParentElement,
  restrictToVerticalAxis,
} from "@dnd-kit/modifiers";
import { CSS } from "@dnd-kit/utilities";
import type { Order } from "@/lib/problems";
import InlineText from "../InlineText";

function GripIcon() {
  return (
    <svg
      className="w-4 h-4 text-fg-faint shrink-0"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <circle cx="5" cy="3" r="1.3" />
      <circle cx="11" cy="3" r="1.3" />
      <circle cx="5" cy="8" r="1.3" />
      <circle cx="11" cy="8" r="1.3" />
      <circle cx="5" cy="13" r="1.3" />
      <circle cx="11" cy="13" r="1.3" />
    </svg>
  );
}

function SortableRow({
  id,
  idx,
  submitted,
  correctIdx,
}: {
  id: string;
  idx: number;
  submitted: boolean;
  correctIdx: number;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled: submitted });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : undefined,
  };

  let cls = "border-border bg-card text-fg";
  if (submitted) {
    cls =
      correctIdx === idx
        ? "border-success-border bg-success-bg text-success-fg"
        : "border-danger-border bg-danger-bg text-danger-fg";
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 text-base border rounded-lg px-4 py-3 min-h-[3.5rem] transition-colors ${cls} ${
        isDragging ? "shadow-lg" : ""
      } ${submitted ? "" : "cursor-grab active:cursor-grabbing select-none"}`}
      {...(submitted ? {} : attributes)}
      {...(submitted ? {} : listeners)}
    >
      <span className="font-mono text-sm text-fg-subtle w-6 text-right shrink-0 select-none">
        {idx + 1}.
      </span>
      <span className="block flex-1 min-w-0">
        <InlineText text={id} />
      </span>
      {submitted ? (
        correctIdx !== idx && (
          <span className="text-xs font-mono text-fg-subtle shrink-0">
            → {correctIdx + 1}
          </span>
        )
      ) : (
        <GripIcon />
      )}
    </div>
  );
}

export default function OrderRenderer({
  problem,
  initialOrder,
  selected,
  onSubmit,
}: {
  problem: Order;
  initialOrder: string[];
  selected: string[] | undefined;
  onSubmit: (ordered: string[]) => void;
}) {
  const submitted = selected !== undefined;
  const [draft, setDraft] = useState<string[]>(initialOrder);
  const display = submitted ? selected : draft;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setDraft((items) => {
      const oldIdx = items.indexOf(String(active.id));
      const newIdx = items.indexOf(String(over.id));
      if (oldIdx < 0 || newIdx < 0) return items;
      return arrayMove(items, oldIdx, newIdx);
    });
  };

  return (
    <div className="flex flex-col gap-3">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
      >
        <SortableContext
          items={display}
          strategy={verticalListSortingStrategy}
        >
          <div className="flex flex-col gap-2">
            {display.map((item, i) => {
              const correctIdx = problem.correct_order.indexOf(item);
              return (
                <SortableRow
                  key={item}
                  id={item}
                  idx={i}
                  submitted={submitted}
                  correctIdx={correctIdx}
                />
              );
            })}
          </div>
        </SortableContext>
      </DndContext>
      {!submitted && (
        <button
          type="button"
          onClick={() => onSubmit(draft)}
          className="self-start mt-1 px-3 py-1.5 rounded-md bg-primary text-white text-sm font-medium cursor-pointer"
        >
          Submit
        </button>
      )}
    </div>
  );
}
