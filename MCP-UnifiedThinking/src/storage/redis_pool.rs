use anyhow::Result;
use redis::aio::MultiplexedConnection;

pub type RedisPool = MultiplexedConnection;

pub async fn create_pool(redis_url: &str) -> Result<RedisPool> {
    let client = redis::Client::open(redis_url)?;
    let pool = client.get_multiplexed_tokio_connection().await?;
    Ok(pool)
}