'use client';

import { TrendingUp } from 'lucide-react';

interface BrandHeaderProps {
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

export default function BrandHeader({ 
  size = 'md', 
  showIcon = true,
  className = '' 
}: BrandHeaderProps) {
  const sizeClasses = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-4xl',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showIcon && (
        <div className="p-1.5 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-lg">
          <TrendingUp className={`${iconSizes[size]} text-white`} />
        </div>
      )}
      <h1 className={`font-display ${sizeClasses[size]} font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300`}>
        Parity
      </h1>
    </div>
  );
}

// Simple text-only version for inline use
export function ParityLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300 ${className}`}>
      Parity
    </span>
  );
}
