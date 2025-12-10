'use client';

import MetricCard from './MetricCard';
import LineChartCard from './LineChartCard';
import InsightList from './InsightList';

export default function DynamicDashboard({ schema }: { schema: any }) {
  if (!schema || !schema.cards) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {schema.cards.map((card: any, i: number) => {
        if (card.type === "metric") return <MetricCard key={i} data={card} />;
        if (card.type === "line_chart") return <div key={i} className="col-span-1 md:col-span-2 lg:col-span-2"><LineChartCard data={card} /></div>;
        if (card.type === "insights") return <InsightList key={i} data={card} />;
        return null;
      })}
    </div>
  );
}
