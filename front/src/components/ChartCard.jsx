import { useEffect, useRef } from "preact/hooks";
import { Chart, ArcElement, BarController, BarElement, CategoryScale, DoughnutController, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip, Filler } from "chart.js";

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

export function ChartCard({ title, subtitle, type, data }) {
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

    chartRef.current = new Chart(canvasRef.current, {
      type,
      data,
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            enabled: true,
          },
        },
        scales:
          type === "line"
            ? {
                x: {
                  ticks: {
                    display: false,
                    color: "#94a3b8",
                  },
                  grid: { color: "rgba(148, 163, 184, 0.15)" },
                },
                y: {
                  ticks: { color: "#94a3b8" },
                  grid: { color: "rgba(148, 163, 184, 0.15)" },
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
    <section className="card chart-card">
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
