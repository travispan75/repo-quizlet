import QuizShell from "./QuizShell";

export default function QuizLayout({
  params,
  children,
}: {
  params: Promise<{ id: string }>;
  children: React.ReactNode;
}) {
  return <QuizShell params={params}>{children}</QuizShell>;
}
