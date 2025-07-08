module.exports = {
  apps: [{
    name: 'unified-intelligence-mcp',
    script: './src/index.js',
    cwd: '/app',
    
    // Instance configuration
    instances: 1,  // Single instance for MCP server
    exec_mode: 'fork',  // Fork mode for single instance
    
    // Auto restart configuration
    autorestart: true,
    watch: false,  // Disable file watching in production
    max_memory_restart: '500M',  // Restart if memory exceeds 500MB
    
    // Logging configuration
    log_file: '/app/logs/combined.log',
    out_file: '/app/logs/out.log',
    error_file: '/app/logs/error.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    
    // Environment variables
    env: {
      NODE_ENV: 'production',
      REDIS_HOST: 'legacymind_redis',
      REDIS_PORT: '6379',
      REDIS_PASSWORD: 'legacymind_redis_20250606',
      MCP_PORT: '3000',
      INSTANCE_ID: 'CC'
    },
    
    // Development environment (if needed)
    env_development: {
      NODE_ENV: 'development',
      REDIS_HOST: 'localhost',
      REDIS_PORT: '6379',
      REDIS_PASSWORD: 'legacymind_redis_20250606',
      MCP_PORT: '3000',
      INSTANCE_ID: 'CC'
    },
    
    // Health monitoring
    health_check_url: 'http://localhost:3000/health',
    health_check_grace_period: 3000,
    
    // Process management
    kill_timeout: 5000,  // 5 seconds to graceful shutdown
    listen_timeout: 3000,
    
    // Error handling
    min_uptime: '10s',  // Minimum uptime before considering stable
    max_restarts: 10,   // Maximum number of restarts within restart_delay
    restart_delay: 4000, // Delay between restarts
    
    // Clustering (disabled for MCP server)
    merge_logs: true,
    
    // Advanced options
    node_args: ['--max-old-space-size=512'],  // Limit memory usage
    
    // Custom startup script options
    args: [],
    
    // Source map support for debugging
    source_map_support: true,
    
    // Disable PM2 internal features we don't need
    pmx: false,
    automation: false
  }],
  
  // Deployment configuration (future use)
  deploy: {
    production: {
      user: 'nodejs',
      host: ['localhost'],
      ref: 'origin/main',
      repo: 'git@github.com:user/repo.git',
      path: '/app',
      'post-deploy': 'npm install && pm2 reload ecosystem.config.cjs --env production',
      env: {
        NODE_ENV: 'production'
      }
    }
  }
};