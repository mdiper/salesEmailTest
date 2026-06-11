# Database: salesemailtool

Tabelle totali: 10

---

## accounts

| Campo             | Tipo         | Null | Key | Default             | Extra          |
|-------------------|--------------|------|-----|---------------------|----------------|
| id                | int(11)      | NO   | PRI | None                | auto_increment |
| email_address     | varchar(255) | NO   | UNI | None                |                |
| provider          | varchar(50)  | NO   |     | None                |                |
| connection_config | longtext     | NO   |     | None                |                |
| oauth_token       | blob         | YES  |     | None                |                |
| status            | varchar(20)  | YES  |     | active              |                |
| last_sync_at      | datetime     | YES  |     | None                |                |
| created_at        | datetime     | YES  |     | current_timestamp() |                |

**Dati (prime 1 righe):**

| id  | email_address       | provider | connection_config                                            | oauth_token | status | last_sync_at | created_at          |
|-----|---------------------|----------|--------------------------------------------------------------|-------------|--------|--------------|---------------------|
| 1   | m.diperna@dafram.it | imap     | {"host": "mail.vianova.it", "port": 993, "username": "m.d... | NULL        | active | NULL         | 2026-06-10 17:02:46 |

---

## audit_log

| Campo       | Tipo         | Null | Key | Default             | Extra          |
|-------------|--------------|------|-----|---------------------|----------------|
| id          | int(11)      | NO   | PRI | None                | auto_increment |
| event_type  | varchar(100) | NO   |     | None                |                |
| entity_type | varchar(50)  | YES  | MUL | None                |                |
| entity_id   | int(11)      | YES  |     | None                |                |
| actor       | varchar(255) | YES  |     | None                |                |
| details     | longtext     | YES  |     | None                |                |
| created_at  | datetime     | YES  | MUL | current_timestamp() |                |

*Tabella vuota.*

---

## content_results

| Campo               | Tipo         | Null | Key | Default             | Extra          |
|---------------------|--------------|------|-----|---------------------|----------------|
| id                  | int(11)      | NO   | PRI | None                | auto_increment |
| email_id            | int(11)      | NO   | UNI | None                |                |
| category            | varchar(50)  | NO   |     | None                |                |
| category_confidence | decimal(3,2) | YES  |     | None                |                |
| summary             | text         | YES  |     | None                |                |
| sentiment           | varchar(20)  | YES  |     | None                |                |
| urgency             | varchar(20)  | YES  |     | None                |                |
| entities            | longtext     | YES  |     | None                |                |
| language            | varchar(10)  | YES  |     | None                |                |
| analyzed_at         | datetime     | YES  |     | current_timestamp() |                |

*Tabella vuota.*

---

## country_results

| Campo            | Tipo         | Null | Key | Default             | Extra          |
|------------------|--------------|------|-----|---------------------|----------------|
| id               | int(11)      | NO   | PRI | None                | auto_increment |
| email_id         | int(11)      | NO   | UNI | None                |                |
| country          | varchar(100) | NO   |     | None                |                |
| country_code     | char(2)      | YES  |     | None                |                |
| confidence       | decimal(3,2) | NO   |     | None                |                |
| detection_method | varchar(50)  | NO   |     | None                |                |
| signals          | longtext     | YES  |     | None                |                |
| analyzed_at      | datetime     | YES  |     | current_timestamp() |                |

*Tabella vuota.*

---

## email_attachments

| Campo        | Tipo          | Null | Key | Default | Extra          |
|--------------|---------------|------|-----|---------|----------------|
| id           | int(11)       | NO   | PRI | None    | auto_increment |
| email_id     | int(11)       | NO   | MUL | None    |                |
| filename     | varchar(512)  | NO   |     | None    |                |
| content_type | varchar(255)  | NO   |     | None    |                |
| size_bytes   | int(11)       | NO   |     | None    |                |
| hash_sha256  | char(64)      | NO   |     | None    |                |
| storage_path | varchar(1024) | YES  |     | None    |                |
| scan_status  | varchar(20)   | YES  |     | pending |                |
| scan_result  | longtext      | YES  |     | None    |                |

*Tabella vuota.*

---

## email_headers

| Campo        | Tipo         | Null | Key | Default | Extra          |
|--------------|--------------|------|-----|---------|----------------|
| id           | int(11)      | NO   | PRI | None    | auto_increment |
| email_id     | int(11)      | NO   | MUL | None    |                |
| header_name  | varchar(255) | NO   |     | None    |                |
| header_value | text         | NO   |     | None    |                |

**Dati (prime 5 righe):**

| id  | email_id | header_name | header_value                                                 |
|-----|----------|-------------|--------------------------------------------------------------|
| 1   | 1        | Return-Path | <info@dafram.it>                                             |
| 2   | 1        | Received    | from mail-66.vianova.it (127.0.0.1)	by mail-66 (Zarafa-sp... |
| 3   | 1        | Received    | from mx-mail-1.vianova.it (unknown [10.128.217.72])	by ma... |
| 4   | 1        | Received    | from localhost (localhost [127.0.0.1])	by mx-mail-1.viano... |
| 5   | 1        | Received    | from mx-mail-1.vianova.it ([127.0.0.1])	by localhost (mx-... |

---

## emails

| Campo             | Tipo         | Null | Key | Default             | Extra                         |
|-------------------|--------------|------|-----|---------------------|-------------------------------|
| id                | int(11)      | NO   | PRI | None                | auto_increment                |
| message_id        | varchar(512) | NO   | UNI | None                |                               |
| account_id        | int(11)      | NO   | MUL | None                |                               |
| from_address      | varchar(320) | NO   | MUL | None                |                               |
| from_display      | varchar(255) | YES  |     | None                |                               |
| to_addresses      | longtext     | NO   |     | None                |                               |
| cc_addresses      | longtext     | YES  |     | None                |                               |
| subject           | text         | YES  |     | None                |                               |
| date_sent         | datetime     | YES  |     | None                |                               |
| date_received     | datetime     | NO   |     | current_timestamp() |                               |
| body_text         | longtext     | YES  |     | None                |                               |
| body_html         | longtext     | YES  |     | None                |                               |
| raw_size_bytes    | int(11)      | YES  |     | None                |                               |
| has_attachments   | tinyint(1)   | YES  |     | 0                   |                               |
| processing_status | varchar(20)  | YES  | MUL | pending             |                               |
| created_at        | datetime     | YES  |     | current_timestamp() |                               |
| updated_at        | datetime     | YES  |     | current_timestamp() | on update current_timestamp() |

**Dati (prime 1 righe):**

| id  | message_id                        | account_id | from_address   | from_display   | to_addresses             | cc_addresses | subject                                  | date_sent           | date_received       | body_text                                                 | body_html | raw_size_bytes | has_attachments | processing_status | created_at          | updated_at          |
|-----|-----------------------------------|------------|----------------|----------------|--------------------------|--------------|------------------------------------------|---------------------|---------------------|-----------------------------------------------------------|-----------|----------------|-----------------|-------------------|---------------------|---------------------|
| 1   | <20260610150025.E14ED85848C@dafy> | 1          | info@dafram.it | info@dafram.it | ["g.palmioli@dafram.it"] | []           | Caricato disegno A09815 con lotti aperti | 2026-06-10 17:00:25 | 2026-06-10 17:03:02 | Elenco dei lotti aperti per A09815 PM2601669 - codint:... | NULL      | 334            | 0               | pending           | 2026-06-10 17:03:02 | 2026-06-10 17:03:02 |

---

## routing_logs

| Campo          | Tipo         | Null | Key | Default             | Extra          |
|----------------|--------------|------|-----|---------------------|----------------|
| id             | int(11)      | NO   | PRI | None                | auto_increment |
| email_id       | int(11)      | NO   | MUL | None                |                |
| rule_id        | int(11)      | YES  | MUL | None                |                |
| rule_name      | varchar(255) | YES  |     | None                |                |
| action_type    | varchar(50)  | NO   |     | None                |                |
| action_details | longtext     | YES  |     | None                |                |
| executed_at    | datetime     | YES  |     | current_timestamp() |                |
| success        | tinyint(1)   | YES  |     | 1                   |                |
| error_message  | text         | YES  |     | None                |                |

*Tabella vuota.*

---

## routing_rules

| Campo           | Tipo         | Null | Key | Default             | Extra                         |
|-----------------|--------------|------|-----|---------------------|-------------------------------|
| id              | int(11)      | NO   | PRI | None                | auto_increment                |
| name            | varchar(255) | NO   |     | None                |                               |
| priority        | int(11)      | NO   | MUL | None                |                               |
| enabled         | tinyint(1)   | YES  |     | 1                   |                               |
| conditions      | longtext     | NO   |     | None                |                               |
| condition_logic | varchar(10)  | YES  |     | AND                 |                               |
| actions         | longtext     | NO   |     | None                |                               |
| stop_processing | tinyint(1)   | YES  |     | 0                   |                               |
| created_by      | varchar(255) | YES  |     | None                |                               |
| created_at      | datetime     | YES  |     | current_timestamp() |                               |
| updated_at      | datetime     | YES  |     | current_timestamp() | on update current_timestamp() |

*Tabella vuota.*

---

## security_results

| Campo          | Tipo                | Null | Key | Default             | Extra          |
|----------------|---------------------|------|-----|---------------------|----------------|
| id             | int(11)             | NO   | PRI | None                | auto_increment |
| email_id       | int(11)             | NO   | UNI | None                |                |
| verdict        | varchar(20)         | NO   |     | None                |                |
| risk_score     | tinyint(3) unsigned | NO   |     | None                |                |
| spf_pass       | tinyint(1)          | YES  |     | None                |                |
| dkim_pass      | tinyint(1)          | YES  |     | None                |                |
| dmarc_pass     | tinyint(1)          | YES  |     | None                |                |
| phishing_score | tinyint(3) unsigned | YES  |     | None                |                |
| flags          | longtext            | YES  |     | None                |                |
| details        | longtext            | YES  |     | None                |                |
| analyzed_at    | datetime            | YES  |     | current_timestamp() |                |

*Tabella vuota.*

---
