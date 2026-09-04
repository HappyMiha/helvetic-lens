export const ASSISTANT_QUESTION_EVENT = "helvetic-lens:assistant-question";

export type AssistantQuestionDetail = {
  comparisonId: string;
  question: string;
};

export function assistantQuestionDetail(event: Event) {
  const detail = (event as CustomEvent<unknown>).detail;
  if (!detail || typeof detail !== "object") return null;
  const candidate = detail as Partial<AssistantQuestionDetail>;
  if (
    typeof candidate.comparisonId !== "string" ||
    typeof candidate.question !== "string" ||
    !candidate.comparisonId ||
    !candidate.question.trim()
  ) {
    return null;
  }
  return {
    comparisonId: candidate.comparisonId,
    question: candidate.question.trim().slice(0, 2000),
  };
}
