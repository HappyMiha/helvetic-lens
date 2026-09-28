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
      <path fill="currentColor" d="M6 6h8v15h20V6h8v36h-8V27H14v15H6z" />
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
