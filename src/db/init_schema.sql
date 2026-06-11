-- ============================================================
-- SalesEmailTool — Schema MySQL (ID progressivi)
-- ============================================================

CREATE DATABASE IF NOT EXISTS salesemailtool
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE salesemailtool;

-- === ACCOUNTS ===

CREATE TABLE IF NOT EXISTS accounts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email_address   VARCHAR(255) UNIQUE NOT NULL,
    provider        VARCHAR(50) NOT NULL COMMENT 'imap, gmail, outlook',
    connection_config JSON NOT NULL,
    oauth_token     BLOB DEFAULT NULL COMMENT 'encrypted at rest',
    status          VARCHAR(20) DEFAULT 'active',
    last_sync_at    DATETIME DEFAULT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- === EMAILS ===

CREATE TABLE IF NOT EXISTS emails (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    message_id          VARCHAR(512) UNIQUE NOT NULL COMMENT 'RFC Message-ID header',
    account_id          INT NOT NULL,
    from_address        VARCHAR(320) NOT NULL,
    from_display        VARCHAR(255) DEFAULT NULL,
    to_addresses        JSON NOT NULL,
    cc_addresses        JSON DEFAULT NULL,
    subject             TEXT DEFAULT NULL,
    date_sent           DATETIME DEFAULT NULL,
    date_received       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    body_text           LONGTEXT DEFAULT NULL,
    body_html           LONGTEXT DEFAULT NULL,
    raw_size_bytes      INT DEFAULT NULL,
    has_attachments     BOOLEAN DEFAULT FALSE,
    processing_status   VARCHAR(20) DEFAULT 'pending' COMMENT 'pending, processing, completed, failed',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX idx_emails_account_date ON emails(account_id, date_received DESC);
CREATE INDEX idx_emails_from ON emails(from_address);
CREATE INDEX idx_emails_status ON emails(processing_status);

-- === HEADERS ===

CREATE TABLE IF NOT EXISTS email_headers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email_id    INT NOT NULL,
    header_name VARCHAR(255) NOT NULL,
    header_value TEXT NOT NULL,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE INDEX idx_headers_email ON email_headers(email_id);

-- === ATTACHMENTS ===

CREATE TABLE IF NOT EXISTS email_attachments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email_id        INT NOT NULL,
    filename        VARCHAR(512) NOT NULL,
    content_type    VARCHAR(255) NOT NULL,
    size_bytes      INT NOT NULL,
    hash_sha256     CHAR(64) NOT NULL,
    storage_path    VARCHAR(1024) DEFAULT NULL COMMENT 'path locale su disco',
    scan_status     VARCHAR(20) DEFAULT 'pending' COMMENT 'pending, clean, infected, error',
    scan_result     JSON DEFAULT NULL,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE INDEX idx_attachments_email ON email_attachments(email_id);

-- === SECURITY RESULTS ===

CREATE TABLE IF NOT EXISTS security_results (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email_id        INT NOT NULL,
    verdict         VARCHAR(20) NOT NULL COMMENT 'SAFE, SUSPICIOUS, DANGEROUS',
    risk_score      TINYINT UNSIGNED NOT NULL COMMENT '0-100',
    spf_pass        BOOLEAN DEFAULT NULL,
    dkim_pass       BOOLEAN DEFAULT NULL,
    dmarc_pass      BOOLEAN DEFAULT NULL,
    phishing_score  TINYINT UNSIGNED DEFAULT NULL,
    flags           JSON DEFAULT NULL,
    details         JSON DEFAULT NULL,
    analyzed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_security_email ON security_results(email_id);

-- === COUNTRY RESULTS ===

CREATE TABLE IF NOT EXISTS country_results (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    email_id            INT NOT NULL,
    country             VARCHAR(100) NOT NULL,
    country_code        CHAR(2) DEFAULT NULL COMMENT 'ISO 3166-1 alpha-2',
    confidence          DECIMAL(3,2) NOT NULL,
    detection_method    VARCHAR(50) NOT NULL,
    signals             JSON DEFAULT NULL,
    analyzed_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_country_email ON country_results(email_id);

-- === CONTENT RESULTS ===

CREATE TABLE IF NOT EXISTS content_results (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    email_id                INT NOT NULL,
    category                VARCHAR(50) NOT NULL,
    category_confidence     DECIMAL(3,2) DEFAULT NULL,
    summary                 TEXT DEFAULT NULL,
    sentiment               VARCHAR(20) DEFAULT NULL,
    urgency                 VARCHAR(20) DEFAULT NULL,
    entities                JSON DEFAULT NULL,
    language                VARCHAR(10) DEFAULT NULL,
    analyzed_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_content_email ON content_results(email_id);

-- === ROUTING RULES ===

CREATE TABLE IF NOT EXISTS routing_rules (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    priority            INT NOT NULL,
    enabled             BOOLEAN DEFAULT TRUE,
    conditions          JSON NOT NULL,
    condition_logic     VARCHAR(10) DEFAULT 'AND',
    actions             JSON NOT NULL,
    stop_processing     BOOLEAN DEFAULT FALSE,
    created_by          VARCHAR(255) DEFAULT NULL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_rules_priority ON routing_rules(priority);

-- === ROUTING LOGS ===

CREATE TABLE IF NOT EXISTS routing_logs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email_id        INT NOT NULL,
    rule_id         INT DEFAULT NULL,
    rule_name       VARCHAR(255) DEFAULT NULL,
    action_type     VARCHAR(50) NOT NULL,
    action_details  JSON DEFAULT NULL,
    executed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    success         BOOLEAN DEFAULT TRUE,
    error_message   TEXT DEFAULT NULL,
    FOREIGN KEY (email_id) REFERENCES emails(id),
    FOREIGN KEY (rule_id) REFERENCES routing_rules(id) ON DELETE SET NULL
);

CREATE INDEX idx_routing_logs_email ON routing_logs(email_id);

-- === AUDIT LOG ===

CREATE TABLE IF NOT EXISTS audit_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    event_type  VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) DEFAULT NULL,
    entity_id   INT DEFAULT NULL,
    actor       VARCHAR(255) DEFAULT NULL,
    details     JSON DEFAULT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_time ON audit_log(created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
