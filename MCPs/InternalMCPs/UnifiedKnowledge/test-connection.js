const { Pool } = require('pg');

async function testConnection() {
  console.log('Testing PostgreSQL connection...');
  console.log('DATABASE_URL:', process.env.DATABASE_URL);
  
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL
  });
  
  try {
    const client = await pool.connect();
    console.log('Connected successfully!');
    
    const result = await client.query('SELECT current_user, current_database()');
    console.log('Query result:', result.rows[0]);
    
    client.release();
    await pool.end();
  } catch (error) {
    console.error('Connection failed:', error.message);
    console.error('Error code:', error.code);
  }
}

testConnection();