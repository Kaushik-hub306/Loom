const domainColors: Record<string, string> = {
  coding: "bg-blue-100 text-blue-700",
  design: "bg-pink-100 text-pink-700",
  devops: "bg-orange-100 text-orange-700",
  security: "bg-red-100 text-red-700",
  testing: "bg-cyan-100 text-cyan-700",
  documentation: "bg-teal-100 text-teal-700",
  performance: "bg-purple-100 text-purple-700",
  architecture: "bg-indigo-100 text-indigo-700",
  general: "bg-gray-100 text-gray-700",
};

const fallbackColors = [
  "bg-fuchsia-100 text-fuchsia-700",
  "bg-lime-100 text-lime-700",
  "bg-rose-100 text-rose-700",
  "bg-violet-100 text-violet-700",
  "bg-sky-100 text-sky-700",
  "bg-amber-100 text-amber-700",
  "bg-emerald-100 text-emerald-700",
];

function hashDomain(domain: string): number {
  let hash = 0;
  for (let i = 0; i < domain.length; i++) {
    hash = ((hash << 5) - hash + domain.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function getColor(domain: string): string {
  if (domainColors[domain]) return domainColors[domain];
  return fallbackColors[hashDomain(domain) % fallbackColors.length];
}

interface Props {
  domain: string;
  size?: "sm" | "md";
}

export default function DomainBadge({ domain, size = "md" }: Props) {
  const colors = getColor(domain);
  const sizeClass = size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2.5 py-0.5 text-sm";

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colors} ${sizeClass}`}>
      {domain}
    </span>
  );
}
