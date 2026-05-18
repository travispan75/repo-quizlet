"use client";

import { use } from "react";
import FileContent from "./FileContent";

export default function QuizPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <FileContent repoId={id} />;
}
