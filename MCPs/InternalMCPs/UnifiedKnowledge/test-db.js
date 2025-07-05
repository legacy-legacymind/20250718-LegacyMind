const { Pool } = require('pg');

const connectionString = process.env.DATABASE_URL || 'postgresql://legacymind:legacymind_db_2025@legacymind_postgres:5432/legacymind';

console.log('Testing connection with:', connectionString);

const pool = new Pool({
  connectionString,
  connectionTimeoutMillis: 5000,
});

async function testConnection() {
  try {
    const client = await pool.connect();
    const result = await client.query('SELECT NOW()');
    console.log('✅ Connection successful!');
    console.log('Current time from DB:', result.rows[0].now);
    client.release();
  } catch (error) {
    console.error('❌ Connection failed:', error.message);
    console.error('Error details:', error);
  } finally {
    await pool.end();
    process.exit(0);
  }
}

testConnection();