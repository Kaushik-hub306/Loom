interface Props {
  confidence: number;
  size?: "sm" | "md";
}

const colorMap: Record<string, string> = {
  low: "bg-rose-100 text-rose-700",
  mid: "bg-amber-100 text-amber-700",
  high: "bg-emerald-100 text-emerald-700",
};

const dotMap: Record<string, string> = {
  low: "bg-rose-500",
  mid: "bg-amber-500",
  high: "bg-emerald-500",
};

function confidenceTier(val: number): "low" | "mid" | "high" {
  if (val <= 3) return "low";
  if (val <= 6) return "mid";
  return "high";
}

export default function ConfidenceBadge({ confidence, size = "md" }: Props) {
  const tier = confidenceTier(confidence);
  const sizeClass = size === "sm" ? "px-1.5 py-0.5 text-xs gap-1" : "px-2.5 py-1 text-sm gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${colorMap[tier]} ${sizeClass}`}
    >
      <span className={`w-2 h-2 rounded-full ${dotMap[tier]}`} />
      <span>{confidence}/10</span>
    </span>
  );
}
