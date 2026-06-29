import { useState, useEffect } from "react";
import client from "../api/client";

export default function Rules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    priority: 50,
    logic: "AND",
    conditions: "",
    actions: "",
    is_active: true,
    stop_processing: false,
  });

  const fetchRules = () => {
    setLoading(true);
    client
      .get("/api/routing-rules")
      .then((res) => setRules(res.data.rules))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      priority: 50,
      logic: "AND",
      conditions: "",
      actions: "",
      is_active: true,
      stop_processing: false,
    });
    setEditingRule(null);
    setShowForm(false);
  };

  const handleEdit = (rule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description || "",
      priority: rule.priority,
      logic: rule.logic || "AND",
      conditions: JSON.stringify(rule.conditions, null, 2),
      actions: JSON.stringify(rule.actions, null, 2),
      is_active: rule.is_active,
      stop_processing: rule.stop_processing || false,
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        priority: Number(formData.priority),
        logic: formData.logic,
        conditions: JSON.parse(formData.conditions),
        actions: JSON.parse(formData.actions),
        is_active: formData.is_active,
        stop_processing: formData.stop_processing,
      };

      if (editingRule) {
        await client.put(`/api/routing-rules/${editingRule.id}`, payload);
      } else {
        await client.post("/api/routing-rules", payload);
      }
      resetForm();
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Eliminare questa regola?")) return;
    try {
      await client.delete(`/api/routing-rules/${id}`);
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.message}`);
    }
  };

  const handleToggle = async (rule) => {
    try {
      await client.put(`/api/routing-rules/${rule.id}`, {
        ...rule,
        is_active: !rule.is_active,
      });
      fetchRules();
    } catch (err) {
      alert(`Errore: ${err.message}`);
    }
  };

  if (loading) return <div className="loading">Caricamento...</div>;

  return (
    <div className="rules-page">
      <div className="page-header">
        <h1>Regole di Routing ({rules.length})</h1>
        <button className="btn-primary" onClick={() => setShowForm(true)}>
          + Nuova Regola
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && resetForm()}>
          <div className="modal">
            <h2>{editingRule ? "Modifica Regola" : "Nuova Regola"}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Nome</label>
                <input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Descrizione</label>
                <input
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Priorita</label>
                  <input
                    type="number"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Logica</label>
                  <select value={formData.logic} onChange={(e) => setFormData({ ...formData, logic: e.target.value })}>
                    <option value="AND">AND</option>
                    <option value="OR">OR</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Condizioni (JSON)</label>
                <textarea
                  rows={5}
                  value={formData.conditions}
                  onChange={(e) => setFormData({ ...formData, conditions: e.target.value })}
                  placeholder='[{"field": "security.verdict", "operator": "equals", "value": "DANGEROUS"}]'
                />
              </div>
              <div className="form-group">
                <label>Azioni (JSON)</label>
                <textarea
                  rows={3}
                  value={formData.actions}
                  onChange={(e) => setFormData({ ...formData, actions: e.target.value })}
                  placeholder='[{"type": "block", "params": {}}]'
                />
              </div>
              <div className="form-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  />
                  Attiva
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.stop_processing}
                    onChange={(e) => setFormData({ ...formData, stop_processing: e.target.checked })}
                  />
                  Stop Processing
                </label>
              </div>
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

      <table className="data-table">
        <thead>
          <tr>
            <th>Priorita</th>
            <th>Nome</th>
            <th>Descrizione</th>
            <th>Logica</th>
            <th>Attiva</th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr key={rule.id} className={!rule.is_active ? "row-disabled" : ""}>
              <td>{rule.priority}</td>
              <td><strong>{rule.name}</strong></td>
              <td>{rule.description || "-"}</td>
              <td>{rule.logic}</td>
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
    </div>
  );
}
