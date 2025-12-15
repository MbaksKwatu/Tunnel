'use client';

import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function LineChartCard({ data }: { data: any }) {
  const { title, data: chartData } = data;

  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="p-6 bg-[#1B1E23] border border-gray-700 rounded-xl col-span-2 lg:col-span-2"
    >
      <h3 className="text-lg font-semibold text-white mb-6">{title}</h3>
      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
            <XAxis 
                dataKey="name" 
                stroke="#666" 
                tick={{fill: '#666', fontSize: 12}} 
                tickLine={false}
                axisLine={false}
            />
            <YAxis 
                stroke="#666" 
                tick={{fill: '#666', fontSize: 12}} 
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `$${value}`}
            />
            <Tooltip 
                contentStyle={{ backgroundColor: '#1B1E23', border: '1px solid #374151', borderRadius: '8px' }}
                itemStyle={{ color: '#fff' }}
            />
            <Line 
                type="monotone" 
                dataKey="value" 
                stroke="#22d3ee" 
                strokeWidth={3} 
                dot={{ fill: '#22d3ee', strokeWidth: 2 }} 
                activeDot={{ r: 6, fill: '#fff' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
