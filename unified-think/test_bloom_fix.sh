#!/bin/bash
export REDIS_PASSWORD=legacymind_redis_pass
export ALLOW_DEFAULT_REDIS_PASSWORD=1

echo '{"jsonrpc":"2.0","method":"ui_think","params":{"thought":"Test thought after bloom filter fix","instance_id":"Claude"},"id":1}' | ./target/release/unified-think