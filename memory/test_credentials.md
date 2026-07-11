# Test Credentials

## Администраторы CRM (JWT auth)
- Email: `admin@crm.ru` | Пароль: `Admin123!` | Роль: admin
- Email: `manager2@crm.ru` | Пароль: `Admin123!` | Роль: admin
- Email: `manager3@crm.ru` | Пароль: `Admin123!` | Роль: admin

## Auth endpoints
- POST /api/auth/login (body: {email, password}) -> {token, user}
- GET /api/auth/me (Authorization: Bearer <token>)
- POST /api/auth/logout
