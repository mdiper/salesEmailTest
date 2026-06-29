import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import client from "../api/client";

function VerdictBadge({ verdict }) {
  const colors = {
    SAFE: "badge-safe",
    SUSPICIOUS: "badge-warning",
    DANGEROUS: "badge-danger",
  };
  return <span className={`badge ${colors[verdict] || ""}`}>{verdict || "-"}</span>;
}

export default function EmailList() {
  const [emails, setEmails] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = parseInt(searchParams.get("page") || "1");
  const perPage = 20;
  const statusFilter = searchParams.get("status") || "";
  const search = searchParams.get("search") || "";

  useEffect(() => {
    setLoading(true);
    const params = { page, per_page: perPage };
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;

    client
      .get("/api/emails", { params })
      .then((res) => {
        setEmails(res.data.emails);
        setTotal(res.data.total);
        setPages(res.data.pages);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, statusFilter, search]);

  const handleSearch = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const q = formData.get("search");
    setSearchParams({ search: q, page: "1" });
  };

  const handleStatusFilter = (status) => {
    const params = { page: "1" };
    if (status) params.status = status;
    if (search) params.search = search;
    setSearchParams(params);
  };

  return (
    <div className="email-list-page">
      <div className="page-header">
        <h1>Email ({total})</h1>
        <form onSubmit={handleSearch} className="search-form">
          <input name="search" defaultValue={search} placeholder="Cerca per mittente o oggetto..." />
          <button type="submit" className="btn-secondary">Cerca</button>
        </form>
      </div>

      <div className="filters">
        <button className={!statusFilter ? "active" : ""} onClick={() => handleStatusFilter("")}>
          Tutte
        </button>
        <button className={statusFilter === "completed" ? "active" : ""} onClick={() => handleStatusFilter("completed")}>
          Completate
        </button>
        <button className={statusFilter === "pending" ? "active" : ""} onClick={() => handleStatusFilter("pending")}>
          Pending
        </button>
        <button className={statusFilter === "failed" ? "active" : ""} onClick={() => handleStatusFilter("failed")}>
          Fallite
        </button>
      </div>

      {loading ? (
        <div className="loading">Caricamento...</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Mittente</th>
                <th>Oggetto</th>
                <th>Categoria</th>
                <th>Risk</th>
                <th>Paese</th>
                <th>Stato</th>
              </tr>
            </thead>
            <tbody>
              {emails.map((email) => (
                <tr key={email.id} onClick={() => navigate(`/emails/${email.id}`)} className="clickable-row">
                  <td className="nowrap">{email.date_received ? new Date(email.date_received).toLocaleDateString("it-IT") : "-"}</td>
                  <td title={email.from_address}>{email.from_display || email.from_address}</td>
                  <td className="subject-cell">{email.subject || "(nessun oggetto)"}</td>
                  <td>{email.category || "-"}</td>
                  <td><VerdictBadge verdict={email.security_verdict} /></td>
                  <td>{email.country_code || "-"}</td>
                  <td><span className={`status-${email.processing_status}`}>{email.processing_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setSearchParams({ ...Object.fromEntries(searchParams), page: String(page - 1) })}>
              Precedente
            </button>
            <span>Pagina {page} di {pages}</span>
            <button disabled={page >= pages} onClick={() => setSearchParams({ ...Object.fromEntries(searchParams), page: String(page + 1) })}>
              Successiva
            </button>
          </div>
        </>
      )}
    </div>
  );
}
