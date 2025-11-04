# ✅ CHECKLIST - Integração Backend ↔ Frontend

## 🎯 Mudanças Realizadas

### ✅ Backend (app.py)
- [x] Campo `titulo` agora é **opcional** (era obrigatório antes)
- [x] Validação do `PUT` melhorada (só atualiza campos enviados)
- [x] CORS já estava correto
- [x] Autenticação Auth0 já estava correta

### ✅ Arquivos Criados
- [x] `.env.example` (backend)
- [x] `.env.example` (frontend)
- [x] `SETUP.md` (guia completo de configuração)
- [x] `README.md` atualizado

---

## 📝 O QUE VOCÊ PRECISA FAZER AGORA:

### 1️⃣ Backend - Configurar Ambiente

```bash
# No diretório raiz do projeto
cp .env.example .env
```

Edite o arquivo `.env` e preencha:

```env
MONGO_URI=mongodb://localhost:27017/tasksdb
AUTH0_DOMAIN=seu-tenant.auth0.com           # ⚠️ PREENCHER
AUTH0_AUDIENCE=https://sua-api-audience     # ⚠️ PREENCHER
FRONTEND_ORIGINS=http://localhost:5173
PORT=5000
FLASK_DEBUG=true
```

### 2️⃣ Frontend - Configurar Ambiente

```bash
cd projeto-zambom-front
cp .env.example .env
```

Edite o arquivo `.env` e preencha:

```env
VITE_AUTH0_DOMAIN=seu-tenant.auth0.com      # ⚠️ PREENCHER (mesmo do backend)
VITE_AUTH0_CLIENT_ID=seu_client_id_aqui    # ⚠️ PREENCHER
VITE_AUTH0_AUDIENCE=https://sua-api-audience # ⚠️ PREENCHER (mesmo do backend)

VITE_API_NOTES_URL=http://localhost:5001
VITE_API_REPORTS_URL=http://localhost:5002
VITE_API_TASKS_URL=http://localhost:5000    # URL do seu backend
```

### 3️⃣ Configurar Auth0 (CRÍTICO!)

📖 **Siga o guia completo em:** `projeto-zambom-front/SETUP.md` seção 2

**Resumo:**

#### A. Criar API no Auth0
1. Acesse Auth0 Dashboard
2. Applications > APIs > Create API
3. **Identifier**: `https://sua-api-audience` (mesmo valor em todos os .env)
4. **Signing Algorithm**: RS256
5. Em **Permissions**, adicione:
   - `create:tasks`
   - `update:tasks`
   - `delete:tasks`
6. Habilite **RBAC** e **Add Permissions in Access Token**

#### B. Criar Application (SPA)
1. Applications > Applications > Create Application
2. Tipo: **Single Page Application**
3. Copie o **Client ID** → `VITE_AUTH0_CLIENT_ID`
4. Configure URLs:
   - **Allowed Callback URLs**: `http://localhost:5173`
   - **Allowed Logout URLs**: `http://localhost:5173`
   - **Allowed Web Origins**: `http://localhost:5173`
   - **Allowed Origins (CORS)**: `http://localhost:5173`
5. Em **Advanced > Grant Types**:
   - ✅ Authorization Code
   - ✅ Refresh Token

#### C. Atribuir Permissões

**Modo Rápido (para desenvolvimento):**

Auth Pipeline > Rules > Create Rule:

```javascript
function addPermissionsToToken(user, context, callback) {
  // Adiciona permissões direto no token
  context.accessToken.scope = context.accessToken.scope + 
    ' create:tasks update:tasks delete:tasks';
  
  callback(null, user, context);
}
```

### 4️⃣ Iniciar MongoDB

```bash
# Docker (recomendado)
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Ou se já tem MongoDB instalado, apenas inicie o serviço
```

### 5️⃣ Instalar Dependências

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd projeto-zambom-front
npm install
```

### 6️⃣ Rodar Aplicação

**Terminal 1 - Backend:**
```bash
python app.py
# Deve mostrar: Running on http://0.0.0.0:5000
```

**Terminal 2 - Frontend:**
```bash
cd projeto-zambom-front
npm run dev
# Deve mostrar: Local: http://localhost:5173
```

### 7️⃣ Testar

1. Abra `http://localhost:5173`
2. Clique em **Login**
3. Faça login com suas credenciais Auth0
4. Teste criar uma tarefa (título é opcional!)
5. Teste editar e deletar

---

## 🚨 Problemas Comuns

### "Insufficient scope" ou 403 Forbidden
**Causa:** Usuário não tem permissões

**Solução:**
1. Verifique se criou a Rule no Auth0 (passo 3C)
2. Limpe o cache: `localStorage.clear()` no console do navegador
3. Faça logout e login novamente

### "CORS policy error"
**Causa:** Backend não aceita requisições do frontend

**Solução:**
- Backend `.env` deve ter: `FRONTEND_ORIGINS=http://localhost:5173`
- Reinicie o backend após mudar

### "Authorization header missing"
**Causa:** Token não está sendo enviado

**Solução:**
1. Verifique se fez login
2. Confira se as 3 variáveis Auth0 estão no frontend `.env`
3. Reinicie o frontend após mudar `.env`

### "Network request failed"
**Causa:** Frontend não consegue acessar backend

**Solução:**
1. Verifique se o backend está rodando: `http://localhost:5000/health`
2. Confirme `VITE_API_TASKS_URL=http://localhost:5000` no frontend

---

## ✨ Diferenças Corrigidas

| Item | Antes (Problema) | Agora (Corrigido) |
|------|------------------|-------------------|
| Campo `titulo` | Obrigatório no backend | **Opcional** (alinhado com frontend) |
| Validação `PUT` | Sempre sobrescrevia todos os campos | Só atualiza campos enviados |
| `.env` no frontend | Não existia | Criado com template |
| `.env` no backend | Não tinha exemplo | Criado `.env.example` |
| Documentação | Mínima | Guia completo de setup |

---

## 📚 Próximos Passos (Opcional)

- [ ] Adicionar testes no backend para o novo comportamento
- [ ] Criar role/user específico no Auth0 para testes
- [ ] Configurar CI/CD
- [ ] Deploy em produção (Render, Railway, etc)

---

**🎉 Pronto! Agora o backend está 100% integrado com o frontend!**

Se tiver qualquer problema, consulte o arquivo `projeto-zambom-front/SETUP.md` para troubleshooting detalhado.
