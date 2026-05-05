# GraphQL API (F12)

## Overview
Add GraphQL API for external integrations.

## Schema Proposal

```graphql
type User {
  id: ID!
  telegramId: Int!
  username: String
  balance: Int!
  createdAt: DateTime!
}

type Transaction {
  id: ID!
  userId: ID!
  amount: Int!
  type: String!
  description: String
  createdAt: DateTime!
}

type ShopItem {
  id: ID!
  name: String!
  description: String
  price: Int!
  category: String!
  itemType: String!
}

type Query {
  user(id: ID!): User
  userByTelegramId(telegramId: Int!): User
  transactions(userId: ID!, limit: Int): [Transaction!]!
  shopItems(category: String): [ShopItem!]!
  balance(userId: ID!): Int!
}

type Mutation {
  accrueCoins(userId: ID!, amount: Int!, description: String): User
  deductCoins(userId: ID!, amount: Int!, description: String): User
  purchaseItem(userId: ID!, itemId: ID!): PurchaseResult
}

type PurchaseResult {
  success: Boolean!
  message: String
  newBalance: Int
}
```

## Implementation

```python
# Example: FastAPI + Strawberry GraphQL
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: strawberry.ID) -> User:
        return get_user_by_id(id)

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
```

## Dependencies
- `strawberry-graphql[fastapi]`
- `fastapi`
