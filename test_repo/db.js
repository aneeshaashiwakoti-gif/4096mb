// db.js — Minimal database client wrapper (test repo file)

'use strict';

const DEFAULT_POOL_SIZE = 10;
const QUERY_TIMEOUT_MS  = 5000;

/**
 * @typedef {Object} QueryResult
 * @property {any[]} rows
 * @property {number} rowCount
 * @property {number} durationMs
 */

// ─────────────────────────────────────────────────────────────────────────────
// Connection pool
// ─────────────────────────────────────────────────────────────────────────────

class ConnectionPool {
  /**
   * @param {string} connectionString
   * @param {number} [poolSize]
   */
  constructor(connectionString, poolSize = DEFAULT_POOL_SIZE) {
    this._cs       = connectionString;
    this._poolSize = poolSize;
    this._pool     = [];
    this._waiting  = [];
  }

  /**
   * Acquire a connection from the pool (or create one if room remains).
   * @returns {Promise<object>} A mock connection handle.
   */
  async acquire() {
    if (this._pool.length > 0) {
      return this._pool.pop();
    }
    if (this._pool.length + this._waiting.length < this._poolSize) {
      return this._createConnection();
    }
    // Wait until a connection is released
    return new Promise((resolve) => this._waiting.push(resolve));
  }

  /**
   * Return a connection to the pool.
   * @param {object} conn
   */
  release(conn) {
    if (this._waiting.length > 0) {
      const next = this._waiting.shift();
      next(conn);
    } else {
      this._pool.push(conn);
    }
  }

  /** @private */
  async _createConnection() {
    // Simulate async connection setup
    await new Promise((r) => setTimeout(r, 10));
    return { id: Math.random().toString(36).slice(2), cs: this._cs };
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Query helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Run a parameterised SQL query and return results.
 *
 * @param {ConnectionPool} pool
 * @param {string}         sql
 * @param {any[]}          [params=[]]
 * @returns {Promise<QueryResult>}
 */
async function query(pool, sql, params = []) {
  const conn  = await pool.acquire();
  const start = Date.now();

  try {
    // In a real driver this would use conn.query(sql, params)
    const rows = await Promise.race([
      _executeQuery(conn, sql, params),
      _timeout(QUERY_TIMEOUT_MS),
    ]);
    return { rows, rowCount: rows.length, durationMs: Date.now() - start };
  } finally {
    pool.release(conn);
  }
}

/** @private */
async function _executeQuery(conn, sql, params) {
  void conn; void sql; void params; // no-op stub
  await new Promise((r) => setTimeout(r, 5));
  return [];
}

/** @private */
function _timeout(ms) {
  return new Promise((_, reject) =>
    setTimeout(() => reject(new Error(`Query timed out after ${ms}ms`)), ms),
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// Transaction helper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Execute *fn* inside a transaction.  Rolls back on any error.
 *
 * @param {ConnectionPool}                  pool
 * @param {(conn: object) => Promise<any>}  fn
 * @returns {Promise<any>}
 */
async function withTransaction(pool, fn) {
  const conn = await pool.acquire();
  try {
    await _executeQuery(conn, 'BEGIN', []);
    const result = await fn(conn);
    await _executeQuery(conn, 'COMMIT', []);
    return result;
  } catch (err) {
    await _executeQuery(conn, 'ROLLBACK', []);
    throw err;
  } finally {
    pool.release(conn);
  }
}


module.exports = { ConnectionPool, query, withTransaction };
