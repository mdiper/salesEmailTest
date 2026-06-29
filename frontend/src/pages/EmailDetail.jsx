import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import client from "../api/client";

function Section({ title, children }) {
  return (
    <div className="detail-section">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function KeyValue({ label, value }) {
  if (value === null || value === undefined) return null;
  const display = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{display}</span>
    </div>
  );
}

export default function EmailDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forwardInfo, setForwardInfo] = useState(null);

  useEffect(() => {
    client
      .get(`/api/emails/${id}`)
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));

    client
      .get(`/api/forwarding/resolve/${id}`)
      .then((res) => setForwardInfo(res.data))
      .catch(() => {});
  }, [id]);

  if (loading) return <div className="loading">Caricamento...</div>;
  if (!data) return <div className="error-msg">Email non trovata</div>;

  const { email, security, country, content, attachments, routing_logs } = data;

  return (
    <div className="email-detail">
      <button className="btn-back" onClick={() => navigate(-1)}>Indietro</button>

      <div className="detail-header">
        <h1>{email.subject || "(nessun oggetto)"}</h1>
        <div className="detail-meta">
          <span>Da: <strong>{email.from_display || email.from_address}</strong></span>
          <span>A: {email.to_addresses}</span>
          <span>Data: {email.date_received ? new Date(email.date_received).toLocaleString("it-IT") : "-"}</span>
          <span>Status: <span className={`status-${email.processing_status}`}>{email.processing_status}</span></span>
        </div>
      </div>

      {email.body_text && (
        <Section title="Corpo Email">
          <pre className="email-body">{email.body_text}</pre>
        </Section>
      )}

      {security && (
        <Section title="Analisi Sicurezza">
          <div className="kv-grid">
            <KeyValue label="Verdict" value={security.verdict} />
            <KeyValue label="Risk Score" value={security.risk_score} />
            <KeyValue label="Header Score" value={security.header_score} />
            <KeyValue label="Phishing Score" value={security.phishing_score} />
            <KeyValue label="Attachment Score" value={security.attachment_score} />
            <KeyValue label="Dettagli" value={security.details} />
          </div>
        </Section>
      )}

      {country && (
        <Section title="Rilevamento Paese">
          <div className="kv-grid">
            <KeyValue label="Paese" value={country.country} />
            <KeyValue label="Codice" value={country.country_code} />
            <KeyValue label="Confidence" value={country.confidence} />
            <KeyValue label="Segnali" value={country.signals} />
          </div>
        </Section>
      )}

      {content && (
        <Section title="Analisi Contenuto">
          <div className="kv-grid">
            <KeyValue label="Categoria" value={content.category} />
            <KeyValue label="Confidence" value={content.category_confidence} />
            <KeyValue label="Summary" value={content.summary} />
            <KeyValue label="Entities" value={content.entities} />
          </div>
        </Section>
      )}

      <Section title="Reindirizzamento">
        {forwardInfo?.recipients?.length > 0 ? (
          <div className="forward-list">
            <div className="forward-country-tag">
              Paese: <strong>{forwardInfo.country}</strong> ({forwardInfo.country_code})
            </div>
            {forwardInfo.recipients.map((email, i) => (
              <div key={i} className="forward-box">
                <span className="forward-label">Destinatario {forwardInfo.recipients.length > 1 ? i + 1 : ""}:</span>
                <span className="forward-email">{email}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted">Nessuna regola di reindirizzamento configurata per il paese di questa email</p>
        )}
      </Section>

      {attachments?.length > 0 && (
        <Section title={`Allegati (${attachments.length})`}>
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Tipo</th>
                <th>Dimensione</th>
                <th>Scan Status</th>
              </tr>
            </thead>
            <tbody>
              {attachments.map((a) => (
                <tr key={a.id}>
                  <td>{a.filename}</td>
                  <td>{a.content_type}</td>
                  <td>{a.size_bytes ? `${(a.size_bytes / 1024).toFixed(1)} KB` : "-"}</td>
                  <td>{a.scan_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {routing_logs?.length > 0 && (
        <Section title="Routing Log">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Regola</th>
                <th>Azione</th>
                <th>Dettaglio</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              {routing_logs.map((log, i) => (
                <tr key={i}>
                  <td>{log.rule_name || log.rule_id}</td>
                  <td>{log.action_type}</td>
                  <td>{log.action_detail || "-"}</td>
                  <td>{log.executed_at ? new Date(log.executed_at).toLocaleString("it-IT") : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </div>
  );
}
