import { useState } from 'react';
import './company-branding.css';

// Set this only to the company's approved logo asset. Until supplied, use an
// honest text wordmark rather than a stock icon that could imply an official logo.
const configuredLogo = import.meta.env.VITE_COMPANY_LOGO_URL || '';

export default function CompanyLogo({
  compact = false,
  className = '',
  name = 'DestinLane',
  subtitle = 'Allied Services Pvt Ltd',
  logoUrl = configuredLogo,
  imageClassName = '',
}) {
  const [failedSource, setFailedSource] = useState(null);
  const showImage = Boolean(logoUrl && failedSource !== logoUrl);

  return (
    <div className={`company-logo flex min-w-0 items-center gap-3 ${className}`}>
      {showImage ? (
        <img
          className={`company-logo-image h-10 w-auto max-w-32 shrink-0 object-contain ${imageClassName}`}
          src={logoUrl}
          alt={compact ? name : ''}
          onError={() => setFailedSource(logoUrl)}
        />
      ) : (
        <span
          className="company-wordmark-initials flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold tracking-[0.08em]"
          aria-hidden={!compact}
          role={compact ? 'img' : undefined}
          aria-label={compact ? name : undefined}
        >DAS</span>
      )}
      {!compact && (
        <div className="min-w-0">
          <p className="company-wordmark-name text-sm font-bold leading-tight tracking-tight text-slate-900">{name}</p>
          {subtitle && <p className="company-wordmark-subtitle mt-1 text-[11px] font-medium leading-tight text-slate-500">{subtitle}</p>}
        </div>
      )}
    </div>
  );
}
