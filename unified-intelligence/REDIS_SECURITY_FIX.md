# Redis Password Security Fix

## Overview
This document describes the security fix applied to remove hardcoded Redis passwords from the codebase.

## Changes Made

### 1. Removed Hardcoded Password
- Previously, the Redis password `"legacymind_redis_pass"` was hardcoded as a fallback in `src/redis.rs`
- This posed a critical security risk as it could expose production Redis instances if environment variables were not properly configured

### 2. Environment Variable Requirements
The application now **requires** one of the following environment variables to be set:
- `REDIS_PASSWORD` (primary)
- `REDIS_PASS` (fallback for compatibility)

If neither is set, the application will panic with a clear error message.

### 3. Backward Compatibility Mode (Temporary)
For local development environments that still use the default password, you can enable backward compatibility by setting:
```bash
export ALLOW_DEFAULT_REDIS_PASSWORD=1
```

**WARNING**: This should ONLY be used for local development and testing. Never use this in production.

### 4. Password Validation
The Redis password is now validated to ensure it doesn't contain URL-unsafe characters that could break the connection string:
- `@` - Would break the URL authority section
- `:` - Would be confused with port separator
- `/` - Would be confused with path separator

If the password contains any of these characters, the application will return a configuration error.

## Migration Instructions

### For Production Environments
1. Ensure `REDIS_PASSWORD` or `REDIS_PASS` environment variable is set with your secure Redis password
2. Remove any reliance on the hardcoded default password
3. Test the connection before deploying

### For Development Environments
Option 1 (Recommended):
```bash
export REDIS_PASSWORD="your_secure_password"
```

Option 2 (Temporary, for backward compatibility):
```bash
export ALLOW_DEFAULT_REDIS_PASSWORD=1
# This will use the legacy password "legacymind_redis_pass"
```

### Example Configuration
```bash
# Production
export REDIS_HOST="redis.example.com"
export REDIS_PORT="6379"
export REDIS_PASSWORD="your_secure_password_here"
export REDIS_DB="0"

# Development (with custom password)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_PASSWORD="dev_password_123"
export REDIS_DB="0"

# Development (with legacy password - NOT RECOMMENDED)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export ALLOW_DEFAULT_REDIS_PASSWORD=1
export REDIS_DB="0"
```

## Security Best Practices

1. **Never commit passwords** to version control
2. **Use strong passwords** in production (at least 16 characters, mix of letters, numbers, special characters)
3. **Rotate passwords regularly** 
4. **Use different passwords** for different environments (dev, staging, production)
5. **Avoid URL-unsafe characters** in passwords to prevent connection issues
6. **Monitor Redis logs** for unauthorized access attempts

## Testing the Changes

After updating your environment variables, test the connection:

```bash
# Set your Redis password
export REDIS_PASSWORD="your_password"

# Run the application
cargo run

# You should see in the logs:
# INFO unified_think::redis: Connecting to Redis at localhost:6379 (db: 0)
# INFO unified_think::redis: Redis connection established
```

If you see an error about missing password, ensure your environment variables are properly set.