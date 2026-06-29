import { useState, useEffect } from "react";
import client from "../api/client";

export default function Forwarding() {
  const [rules, setRules] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [formData, setFormData] = useState({
    country_code: "",
    country_name: "",
    forward_to: "",
    is_active: true,
  });

  const fetchRules = () => {
    setLoading(true);
    client
      .get("/api/forwarding")
      .then((res) => setRules(res.data.rules))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const fetchCountries = () => {
    client
      .get("/api/forwarding/countries")
      .then((res) => setCountries(res.data.countries))
      .catch(console.error);
  };

  useEffect(() => {
    fetchRules();
    fetchCountries();
  }, []);

  const resetForm = () => {
    setFormData({ country_code: "", country_name: "", forward_to: "", is_active: true });
    setEditingRule(null);
    setShowForm(false);
  };

  const handleEdit = (rule) => {
    setEditingRule(rule);
    setFormData({
      country_code: rule.country_code,
      country_name: rule.country_name,
      forward_to: rule.forward_to,
      is_active: rule.is_active,
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingRule) {
        await client.put(`/api/forwarding/${editingRule.id}`, {
          country_name: formData.country_name,
          forward_to: formData.forward_to,
          is_active: formData.is_active,
        });
      } else {
        await client.post("/api/forwarding", {
          country_code: formData.country_code.toUpperCase(),
          country_name: formData.country_name,
          forward_to: formData.forward_to,
          is_active: formData.is_active,
        });
      }
      resetForm();
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Eliminare questa regola di reindirizzamento?")) return;
    try {
      await client.delete(`/api/forwarding/${id}`);
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.message}`);
    }
  };

  const handleToggle = async (rule) => {
    try {
      await client.put(`/api/forwarding/${rule.id}`, { is_active: !rule.is_active });
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.message}`);
    }
  };

  if (loading) return <div className="loading">Caricamento...</div>;

  return (
    <div className="forwarding-page">
      <div className="page-header">
        <h1>Reindirizzamenti per Paese ({rules.length})</h1>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          + Nuovo Reindirizzamento
        </button>
      </div>

      <p className="page-description">
        Configura a quale indirizzo email vengono reindirizzate le email in base al paese di origine del mittente.
      </p>

      {showForm && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && resetForm()}>
          <div className="modal">
            <h2>{editingRule ? "Modifica Reindirizzamento" : "Nuovo Reindirizzamento"}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Paese</label>
                <select
                  value={formData.country_code}
                  onChange={(e) => {
                    const selected = countries.find((c) => c.country_code === e.target.value);
                    setFormData({
                      ...formData,
                      country_code: e.target.value,
                      country_name: selected?.country || "",
                    });
                  }}
                  disabled={!!editingRule}
                  required
                >
                  <option value="">-- Seleziona paese --</option>
                  {countries.map((c) => (
                    <option key={c.country_code} value={c.country_code}>
                      {c.country} ({c.country_code})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Indirizzo Email Destinatario</label>
                <input
                  type="email"
                  value={formData.forward_to}
                  onChange={(e) => setFormData({ ...formData, forward_to: e.target.value })}
                  placeholder="commerciale-italia@azienda.it"
                  required
                />
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                Attivo
              </label>
              <div className="form-actions">
                <button type="button" className="btn-secondary" onClick={resetForm}>
                  Annulla
                </button>
                <button type="submit" className="btn-primary">
                  {editingRule ? "Salva" : "Crea"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {rules.length === 0 ? (
        <div className="empty-state">
          <p>Nessuna regola di reindirizzamento configurata.</p>
          <p>Clicca "Nuovo Reindirizzamento" per associare un paese a un destinatario email.</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Paese</th>
              <th>Codice</th>
              <th>Destinatario</th>
              <th>Attivo</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id} className={!rule.is_active ? "row-disabled" : ""}>
                <td><strong>{rule.country_name}</strong></td>
                <td>{rule.country_code}</td>
                <td className="forward-email-cell">{rule.forward_to}</td>
                <td>
                  <button
                    className={`toggle-btn ${rule.is_active ? "active" : ""}`}
                    onClick={() => handleToggle(rule)}
                  >
                    {rule.is_active ? "ON" : "OFF"}
                  </button>
                </td>
                <td className="action-cell">
                  <button className="btn-sm" onClick={() => handleEdit(rule)}>Modifica</button>
                  <button className="btn-sm btn-danger" onClick={() => handleDelete(rule.id)}>Elimina</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
