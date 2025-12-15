'use client';

import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function MetricCard({ data }: { data: any }) {
  const { title, value, trend, status } = data;

  const getStatusColor = () => {
    if (status === 'positive') return 'text-green-400';
    if (status === 'negative') return 'text-red-400';
    return 'text-gray-400';
  };

  const getIcon = () => {
    if (status === 'positive') return <TrendingUp className="w-4 h-4" />;
    if (status === 'negative') return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  };

  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="p-6 bg-[#1B1E23] border border-gray-700 rounded-xl"
    >
      <h3 className="text-sm text-gray-400 mb-2">{title}</h3>
      <div className="flex items-end justify-between">
        <span className="text-3xl font-bold text-white">{value}</span>
        <div className={`flex items-center gap-1 ${getStatusColor()} text-sm font-medium`}>
          {getIcon()}
          <span>{trend}</span>
        </div>
      </div>
    </motion.div>
  );
}
