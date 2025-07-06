import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class MigrationRunner {
  constructor(postgresManager) {
    this.postgresManager = postgresManager;
    this.migrationsDir = path.join(__dirname, '..', 'migrations');
  }

  async run() {
    console.log('Starting database migrations...');
    
    try {
      // Ensure migrations table exists
      await this.ensureMigrationsTable();
      
      // Get all migration files
      const migrationFiles = await this.getMigrationFiles();
      
      // Get applied migrations
      const appliedMigrations = await this.getAppliedMigrations();
      
      // Filter pending migrations
      const pendingMigrations = migrationFiles.filter(
        file => !appliedMigrations.includes(file)
      );
      
      if (pendingMigrations.length === 0) {
        console.log(`No pending migrations. ${appliedMigrations.length} migration(s) already applied.`);
        return;
      }
      
      // Apply pending migrations
      for (const migrationFile of pendingMigrations) {
        await this.applyMigration(migrationFile);
      }
      
      console.log(`Successfully applied ${pendingMigrations.length} migration(s).`);
    } catch (error) {
      console.error('Migration failed:', error);
      throw error;
    }
  }
  
  async ensureMigrationsTable() {
    const query = `
      CREATE TABLE IF NOT EXISTS migrations (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(255) UNIQUE NOT NULL,
        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      );
    `;
    
    await this.postgresManager.pool.query(query);
  }
  
  async getMigrationFiles() {
    try {
      const files = await fs.readdir(this.migrationsDir);
      
      // Filter SQL files and sort them
      return files
        .filter(file => file.endsWith('.sql'))
        .sort((a, b) => a.localeCompare(b));
    } catch (error) {
      if (error.code === 'ENOENT') {
        console.log(`Migrations directory not found: ${this.migrationsDir}`);
        return [];
      }
      throw error;
    }
  }
  
  async getAppliedMigrations() {
    const query = 'SELECT filename FROM migrations ORDER BY filename';
    const result = await this.postgresManager.pool.query(query);
    return result.rows.map(row => row.filename);
  }
  
  async applyMigration(filename) {
    console.log(`Applying migration: ${filename}`);
    
    const filePath = path.join(this.migrationsDir, filename);
    const sql = await fs.readFile(filePath, 'utf8');
    
    // Start a transaction
    const client = await this.postgresManager.pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Execute the migration
      await client.query(sql);
      
      // Record the migration
      await client.query(
        'INSERT INTO migrations (filename) VALUES ($1)',
        [filename]
      );
      
      await client.query('COMMIT');
      console.log(`✓ Applied migration: ${filename}`);
    } catch (error) {
      await client.query('ROLLBACK');
      console.error(`✗ Failed to apply migration ${filename}:`, error);
      throw error;
    } finally {
      client.release();
    }
  }
}

// Export a function that creates and runs the migration runner
export async function runMigrations(postgresManager) {
  const runner = new MigrationRunner(postgresManager);
  await runner.run();
}