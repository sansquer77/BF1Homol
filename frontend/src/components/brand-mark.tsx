import Image from "next/image";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  const size = compact ? 38 : 52;

  return (
    <span className={compact ? "brand brand--compact" : "brand"} aria-label="BF1 · Bolão Fórmula 1">
      <Image className="brand__icon" src="/bf1-icon.png" width={size} height={size} sizes={`${size}px`} alt="" priority />
      <span className="brand__copy">
        <strong>BF1</strong>
        {compact ? null : <small>Bolão Fórmula 1</small>}
      </span>
    </span>
  );
}
