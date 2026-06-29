import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import client from "../api/client";

const COLORS = ["#4f46e5", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client
      .get("/api/stats")
      .then((res) => setStats(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Caricamento statistiche...</div>;
  if (!stats) return <div className="error-msg">Errore nel caricamento</div>;

  const riskData = Object.entries(stats.by_risk_band || {}).map(([name, value]) => ({
    name,
    value,
  }));

  const categoryData = Object.entries(stats.by_category || {}).map(([name, value]) => ({
    name,
    value,
  }));

  const verdictData = Object.entries(stats.by_verdict || {}).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>

      <div className="stats-cards">
        <div className="stat-card">
          <h3>Email Totali</h3>
          <span className="stat-number">{stats.total_emails}</span>
        </div>
        <div className="stat-card">
          <h3>Processate</h3>
          <span className="stat-number">{stats.by_status?.completed || 0}</span>
        </div>
        <div className="stat-card">
          <h3>In Coda</h3>
          <span className="stat-number">{stats.by_status?.pending || 0}</span>
        </div>
        <div className="stat-card">
          <h3>Paesi Rilevati</h3>
          <span className="stat-number">{stats.by_country?.length || 0}</span>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <h3>Email per Giorno (ultimi 30 giorni)</h3>
          {stats.emails_per_day?.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={stats.emails_per_day}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="no-data">Nessun dato disponibile</p>
          )}
        </div>

        <div className="chart-card">
          <h3>Distribuzione Risk Score</h3>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={riskData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {riskData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="no-data">Nessun dato disponibile</p>
          )}
        </div>

        <div className="chart-card">
          <h3>Verdict Sicurezza</h3>
          {verdictData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={verdictData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {verdictData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="no-data">Nessun dato disponibile</p>
          )}
        </div>

        <div className="chart-card">
          <h3>Categorie Contenuto</h3>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={categoryData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" width={120} />
                <Tooltip />
                <Bar dataKey="value" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="no-data">Nessun dato disponibile</p>
          )}
        </div>
      </div>

      {stats.by_country?.length > 0 && (
        <div className="chart-card full-width">
          <h3>Top 10 Paesi</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Paese</th>
                <th>Codice</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_country.map((c) => (
                <tr key={c.code}>
                  <td>{c.country}</td>
                  <td>{c.code}</td>
                  <td>{c.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
