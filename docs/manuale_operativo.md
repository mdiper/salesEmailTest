# SalesEmailTool — Manuale Operativo

Guida pratica per le operazioni ricorrenti sul sistema.

---

## 1. Gestione Account

### Inserire un nuovo account email

```sql
INSERT INTO accounts (email_address, provider, connection_config, status)
VALUES (
    'nome@dominio.it',
    'imap',
    '{"host": "mail.dominio.it", "port": 993, "username": "nome@dominio.it", "use_ssl": true}',
    'active'
);
```

**Campi:**

| Campo             | Descrizione                                      | Esempio                  |
|-------------------|--------------------------------------------------|--------------------------|
| email_address     | Indirizzo email completo                         | `nome@dominio.it`        |
| provider          | Tipo protocollo: `imap`, `gmail`, `outlook`      | `imap`                   |
| connection_config | JSON con parametri di connessione                | vedi sopra               |
| status            | `active` oppure `disabled`                       | `active`                 |

### Verificare gli account presenti

```sql
SELECT id, email_address, provider, status, last_sync_at
FROM accounts
ORDER BY id;
```

### Disabilitare un account

```sql
UPDATE accounts SET status = 'disabled' WHERE email_address = 'nome@dominio.it';
```

---
