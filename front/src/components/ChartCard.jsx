import { useEffect, useRef } from "preact/hooks";
import { Chart, ArcElement, BarController, BarElement, CategoryScale, DoughnutController, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip, Filler } from "chart.js";

const rankGuides = [
  { tier: "Iron", value: 0, color: "rgba(236, 251, 255, 0.42)" },
  { tier: "Bronze", value: 400, color: "rgba(231, 151, 61, 0.62)" },
  { tier: "Silver", value: 800, color: "rgba(236, 251, 255, 0.58)" },
  { tier: "Gold", value: 1200, color: "rgba(255, 218, 91, 0.78)" },
  { tier: "Platinum", value: 1600, color: "rgba(127, 218, 255, 0.7)" },
  { tier: "Emerald", value: 2000, color: "rgba(116, 244, 188, 0.68)" },
  { tier: "Diamond", value: 2400, color: "rgba(236, 251, 255, 0.7)" },
  { tier: "Master", value: 2800, color: "rgba(127, 218, 255, 0.76)" },
  { tier: "Grandmaster", value: 3200, color: "rgba(255, 218, 91, 0.78)" },
  { tier: "Challenger", value: 3600, color: "rgba(116, 244, 188, 0.74)" },
];

const rankIconCache = new Map();

Chart.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  Filler,
);

function getRankIcon(tier, chart) {
  if (typeof window === "undefined") {
    return null;
  }

  const cachedIcon = rankIconCache.get(tier);
  if (cachedIcon) {
    return cachedIcon;
  }

  const icon = new Image();
  icon.onload = () => chart.draw();
  icon.src = `/api/assets/elo/elo/Rank=${tier}.png`;
  rankIconCache.set(tier, icon);
  return icon;
}

function buildLineGradient(context) {
  const chart = context.chart;
  const chartArea = chart.chartArea;

  if (!chartArea) {
    return "#f2b533";
  }

  const gradient = chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  gradient.addColorStop(0, "#a9efff");
  gradient.addColorStop(0.2, "#6ef4b5");
  gradient.addColorStop(0.5, "#f7c241");
  gradient.addColorStop(1, "#e6972f");
  return gradient;
}

function buildLineData(data) {
  return {
    ...data,
    datasets: (data?.datasets || []).map((dataset) => ({
      ...dataset,
      borderColor: buildLineGradient,
      backgroundColor: "rgba(247, 194, 65, 0.05)",
      borderWidth: 4,
      tension: 0.44,
      cubicInterpolationMode: "monotone",
      fill: false,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHitRadius: 18,
      pointBackgroundColor: "#f8d568",
      pointBorderColor: "#eafcff",
      pointBorderWidth: 2,
    })),
  };
}

const rankedLinePlugin = {
  id: "rankedLinePlugin",
  beforeDatasetsDraw(chart) {
    if (chart.config.type !== "line" || !chart.options.plugins?.rankedLine?.enabled) {
      return;
    }

    const { ctx, chartArea, scales } = chart;
    const yScale = scales.y;

    if (!chartArea || !yScale) {
      return;
    }

    const visibleGuides = rankGuides.filter((guide) => guide.value >= yScale.min && guide.value <= yScale.max);

    ctx.save();
    ctx.setLineDash([7, 8]);
    ctx.lineWidth = 1.2;

    visibleGuides.forEach((guide) => {
      const y = yScale.getPixelForValue(guide.value);
      ctx.strokeStyle = guide.color;
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();

      const icon = getRankIcon(guide.tier, chart);
      const iconSize = 26;
      const iconX = chartArea.left - iconSize - 11;
      const iconY = y - iconSize / 2;

      if (icon?.complete && icon.naturalWidth > 0) {
        ctx.save();
        ctx.shadowColor = "rgba(0, 0, 0, 0.38)";
        ctx.shadowBlur = 10;
        ctx.drawImage(icon, iconX, iconY, iconSize, iconSize);
        ctx.restore();
      }
    });

    ctx.restore();
  },
};

Chart.register(rankedLinePlugin);

export function ChartCard({ title, subtitle, type, data, variant }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    if (!canvasRef.current || !data?.labels?.length) {
      return undefined;
    }

    const isLineChart = type === "line";
    const isRankedLineChart = isLineChart && variant === "ranked";

    chartRef.current = new Chart(canvasRef.current, {
      type,
      data: isRankedLineChart ? buildLineData(data) : data,
      options: {
        responsive: true,
        maintainAspectRatio: true,
        layout: isRankedLineChart
          ? {
              padding: {
                top: 12,
                right: 8,
                bottom: 6,
                left: 44,
              },
            }
          : undefined,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            enabled: true,
            displayColors: !isRankedLineChart,
            backgroundColor: isRankedLineChart ? undefined : undefined,
            borderColor: isRankedLineChart ? "rgba(127, 218, 255, 0.55)" : undefined,
            borderWidth: isRankedLineChart ? 1 : undefined,
            titleColor: isRankedLineChart ? "#eafcff" : undefined,
            bodyColor: isRankedLineChart ? "#ffd45d" : undefined,
            padding: isRankedLineChart ? 10 : undefined,
            cornerRadius: isRankedLineChart ? 6 : undefined,
            callbacks: isRankedLineChart
              ? {
                  label(context) {
                    const hoverLabel = context.dataset.hoverLabels?.[context.dataIndex];
                    return hoverLabel || `${context.dataset.label}: ${context.formattedValue}`;
                  },
                }
              : undefined,
          },
          rankedLine: {
            enabled: isRankedLineChart,
          },
        },
        scales:
          isLineChart
            ? {
                x: {
                  border: {
                    display: false,
                  },
                  ticks: {
                    display: false,
                  },
                  grid: {
                    display: !isRankedLineChart,
                    drawBorder: false,
                    color: "rgba(148, 163, 184, 0.15)",
                  },
                },
                y: {
                  border: {
                    display: false,
                  },
                  ticks: {
                    display: !isRankedLineChart,
                    color: "#94a3b8",
                    count: isRankedLineChart ? rankGuides.length : undefined,
                  },
                  grid: {
                    display: !isRankedLineChart,
                    drawBorder: false,
                    color: "rgba(148, 163, 184, 0.15)",
                  },
                },
              }
            : undefined,
        elements: isRankedLineChart
          ? {
              line: {
                borderCapStyle: "round",
                borderJoinStyle: "round",
              },
            }
          : undefined,
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [data, type]);

  return (
    <section className={`card chart-card${type === "line" && variant === "ranked" ? " chart-card-line" : ""}`}>
      <div className="section-header">
        <div>
          <p className="eyebrow">Visualisation</p>
          <h3>{title}</h3>
          {/* {subtitle ? <p className="muted">{subtitle}</p> : null} */}
        </div>
      </div>
      <div className="chart-frame">
        {data?.labels?.length ? <canvas ref={canvasRef} /> : <p className="empty-inline">Pas encore de données.</p>}
      </div>
    </section>
  );
}
