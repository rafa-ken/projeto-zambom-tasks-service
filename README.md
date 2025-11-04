# � Tasks Service - Backend + Frontend

Sistema completo de gerenciamento de tarefas com autenticação Auth0 e integração entre backend Flask e frontend React.

## 🏗️ Arquitetura

- **Backend**: Flask + MongoDB + Auth0 (JWT)
- **Frontend**: React + Vite + Auth0 React SDK
- **Autenticação**: Auth0 com RBAC (Role-Based Access Control)

## 🚀 Quick Start

### 1️⃣ Backend Setup

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais Auth0 e MongoDB

# Iniciar servidor
python app.py
```

Backend rodará em: `http://localhost:5000`

### 2️⃣ Frontend Setup

```bash
cd projeto-zambom-front

# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais Auth0

# Iniciar aplicação
npm run dev
```

Frontend rodará em: `http://localhost:5173`

## 📋 Configuração Detalhada

**🔴 IMPORTANTE:** Consulte o arquivo [projeto-zambom-front/SETUP.md](projeto-zambom-front/SETUP.md) para instruções completas de:
- Configuração do Auth0 (API, Application, Permissions)
- Variáveis de ambiente
- Troubleshooting
- Deploy

## 🔐 Autenticação

O sistema usa Auth0 com as seguintes permissões (scopes):

- `create:tasks` - Criar tarefas
- `update:tasks` - Atualizar tarefas
- `delete:tasks` - Deletar tarefas

## 📡 API Endpoints

### Tarefas

| Método | Endpoint | Scope | Descrição |
|--------|----------|-------|-----------|
| GET | `/health` | - | Health check |
| GET | `/tarefas` | auth | Listar todas as tarefas |
| POST | `/tarefas` | `create:tasks` | Criar nova tarefa |
| PUT | `/tarefas/:id` | `update:tasks` | Atualizar tarefa |
| DELETE | `/tarefas/:id` | `delete:tasks` | Deletar tarefa |

### Request/Response Examples

**POST /tarefas**
```json
{
  "titulo": "Minha tarefa (opcional)",
  "descricao": "Descrição da tarefa",
  "concluida": false
}
```

**Response**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "titulo": "Minha tarefa",
  "descricao": "Descrição da tarefa",
  "concluida": false
}
```

## 🧪 Testes

```bash
# Rodar testes
pytest tests/

# Com coverage
pytest --cov=. tests/
```

## 🐳 Docker

```bash
# Build
docker build -t tasks-service .

# Run
docker run -p 5000:5000 --env-file .env tasks-service
```

## ⚙️ Variáveis de Ambiente

### Backend (.env)

```env
MONGO_URI=mongodb://localhost:27017/tasksdb
AUTH0_DOMAIN=seu-tenant.auth0.com
AUTH0_AUDIENCE=https://sua-api-audience
FRONTEND_ORIGINS=http://localhost:5173
PORT=5000
FLASK_DEBUG=true
```

### Frontend (.env)

```env
VITE_AUTH0_DOMAIN=seu-tenant.auth0.com
VITE_AUTH0_CLIENT_ID=seu_client_id
VITE_AUTH0_AUDIENCE=https://sua-api-audience
VITE_API_TASKS_URL=http://localhost:5000
```

## 🔧 Troubleshooting

### CORS Error
- Verifique se `FRONTEND_ORIGINS` no backend inclui a URL do frontend
- Frontend: `http://localhost:5173`

### 401 Unauthorized
- Verifique se o token Auth0 está sendo enviado
- Confirme que `AUTH0_DOMAIN` e `AUTH0_AUDIENCE` estão corretos em ambos (backend e frontend)

### 403 Forbidden
- Usuário não tem as permissões necessárias
- Configure as permissions no Auth0 (veja [SETUP.md](projeto-zambom-front/SETUP.md))

### Token expirado
- O frontend usa refresh tokens automaticamente
- Limpe o localStorage e faça login novamente: `localStorage.clear()`

## 📝 Notas Importantes

1. **Campo `titulo` é opcional** - O backend aceita tarefas sem título
2. **CORS está configurado** - Suporta múltiplas origens via `FRONTEND_ORIGINS`
3. **Scopes são validados** - Cada operação requer permissões específicas
4. **Refresh tokens habilitados** - Usuário permanece autenticado