#!/usr/bin/env node

import { PostgreSQLManager } from './src/managers/postgresql-manager.js';
import { runMigrations } from './src/utils/run-migrations.js';

async function testMigrations() {
  console.log('Testing migration runner...');
  
  const dbUrl = process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/postgres';
  const postgres = new PostgreSQLManager({ connectionString: dbUrl });
  
  try {
    // Connect to database
    console.log('Connecting to PostgreSQL...');
    await postgres.connect();
    
    // Run migrations
    console.log('Running migrations...');
    await runMigrations(postgres);
    
    // Verify schema
    console.log('Verifying schema...');
    const schemaResult = await postgres.verifySchema();
    console.log('Schema verification result:', schemaResult);
    
    // Check migrations table
    const result = await postgres.pool.query('SELECT * FROM migrations ORDER BY applied_at');
    console.log('Applied migrations:', result.rows);
    
  } catch (error) {
    console.error('Test failed:', error);
    process.exit(1);
  } finally {
    await postgres.disconnect();
  }
  
  console.log('Migration test completed successfully!');
}

testMigrations().catch(console.error);