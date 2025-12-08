'use client';

import { motion } from 'framer-motion';
import { Lightbulb } from 'lucide-react';

export default function InsightList({ data }: { data: any }) {
  const { title, items } = data;

  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="p-6 bg-[#1B1E23] border border-gray-700 rounded-xl"
    >
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="w-5 h-5 text-yellow-400" />
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      <ul className="space-y-3">
        {items.map((item: string, i: number) => (
          <li key={i} className="flex gap-3 text-gray-300 text-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
            {item}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}
