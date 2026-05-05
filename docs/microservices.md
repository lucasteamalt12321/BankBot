# Microservices Architecture (F11)

## Current State
Single monolithic bot (`bot/bot.py`).

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway                            │
│              (telegram-bot-gateway)                      │
└─────────────────┬───────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬─────────────┐
    ▼             ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
│ Bank   │  │ Bridge   │  │ Parser  │  │ Shop     │
│ Service│  │ Service  │  │ Service │  │ Service  │
└────────┘  └──────────┘  └─────────┘  └──────────┘
    │             │             │             │
    └─────────────┴─────────────┴─────────────┘
                  │
           ┌──────▼──────┐
           │   PostgreSQL │
           │   + Redis   │
           └─────────────┘
```

## Services

### 1. Bank Service
- Balance management
- Transactions
- User management

### 2. Bridge Service  
- Telegram → VK forwarding
- Media handling
- Rate limiting

### 3. Parser Service
- Message parsing
- Game integration
- Webhook handlers

### 4. Shop Service
- Items management
- Purchases
- Inventory

## Implementation Steps

1. Extract services one by one
2. Add service discovery (Consul/Etcd)
3. Add API gateway
4. Add message queue (RabbitMQ/Kafka)

## Tech Stack
- **Container**: Docker + Docker Compose
- **Service**: FastAPI or Flask
- **Message Queue**: Redis Streams
- **Service Discovery**: Consul
- **Monitoring**: Prometheus + Grafana
