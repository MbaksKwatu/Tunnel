'use client';

import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  comingSoon?: boolean;
  children?: React.ReactNode;
}

export default function FeatureCard({ 
  icon: Icon, 
  title, 
  description, 
  comingSoon = false,
  children 
}: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      whileHover={{ 
        scale: 1.03,
      }}
      className="p-6 bg-base-900 shadow-inner-dark border border-gray-800 rounded-2xl hover:border-accent-indigo hover:shadow-glow-indigo transition-all duration-200 cursor-pointer"
    >
      <div className="flex items-center gap-3 mb-3">
        <Icon className="h-5 w-5 text-accent-cyan" />
        <h3 className="text-lg font-semibold text-gray-200">{title}</h3>
      </div>
      <p className="text-sm text-gray-400 mb-4">{description}</p>
      {comingSoon && (
        <span className="inline-block text-xs bg-accent-indigo/10 text-accent-indigo px-2 py-1 rounded-md">
          Coming soon
        </span>
      )}
      {children && (
        <div className="mt-4">
          {children}
        </div>
      )}
    </motion.div>
  );
}

