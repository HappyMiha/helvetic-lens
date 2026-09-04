type BrandMarkProps = {
  className?: string;
  title?: string;
};

export function BrandMark({ className = "", title }: BrandMarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 48"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      xmlns="http://www.w3.org/2000/svg"
    >
      {title && <title>{title}</title>}
      <rect width="48" height="48" rx="14" fill="#101936" />
      <circle
        cx="23"
        cy="24"
        r="11.5"
        fill="none"
        stroke="#86A5FF"
        strokeWidth="2.25"
      />
      <path
        d="M23 16.5v15M15.5 24h15"
        fill="none"
        stroke="white"
        strokeLinecap="round"
        strokeWidth="3.75"
      />
      <path
        d="M31.1 32.2 37 38"
        fill="none"
        stroke="#86A5FF"
        strokeLinecap="round"
        strokeWidth="3"
      />
      <circle cx="37" cy="11" r="3.5" fill="#FF5A5F" />
    </svg>
  );
}

export function BrandLockup({
  inverse = false,
  className = "",
}: {
  inverse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`brand-lockup ${className}`.trim()}
      data-inverse={inverse || undefined}
    >
      <BrandMark className="brand-lockup-mark" />
      <span className="brand-lockup-name">Helvetic Lens</span>
    </span>
  );
}
