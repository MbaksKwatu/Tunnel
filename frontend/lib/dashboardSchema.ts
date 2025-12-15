export const initialDashboardSchema = {
  cards: [
    {
      type: "metric",
      title: "Total Revenue (YTD)",
      value: "$1.2M",
      trend: "+12%",
      status: "positive"
    },
    {
      type: "metric",
      title: "Operating Expenses",
      value: "$850K",
      trend: "-5%",
      status: "positive"
    },
    {
        type: "metric",
        title: "Net Profit",
        value: "$350K",
        trend: "+28%",
        status: "positive"
    },
    {
        type: "metric",
        title: "Cash Burn",
        value: "$45K/mo",
        trend: "+2%",
        status: "warning"
    },
    {
      type: "line_chart",
      title: "Revenue vs Expenses",
      data: [
        { name: "Jan", value: 100 },
        { name: "Feb", value: 120 },
        { name: "Mar", value: 110 },
        { name: "Apr", value: 140 },
        { name: "May", value: 150 },
        { name: "Jun", value: 170 }
      ]
    },
    {
      type: "insights",
      title: "AI Observations",
      items: [
        "Revenue growth is outpacing expense growth.",
        "Q2 showed strongest profitability margins.",
        "Cash burn remains within safe runway limits (18 months)."
      ]
    }
  ]
};
