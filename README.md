# 📋 Tasks Service

Serviço responsável pelo **CRUD de tarefas**.

## 🚀 Funcionalidades
- Criar tarefa (`POST /tasks`)
- Listar tarefas (`GET /tasks`)
- Atualizar tarefa (`PUT /tasks/<id>`)
- Deletar tarefa (`DELETE /tasks/<id>`)

## 🏗 Arquitetura
- Python 3.10
- Flask + SQLAlchemy (ou MongoDB em versão futura)
- Testes com Pytest
- Autenticação OAuth2 via Auth0 (simulada nesta fase)
- Docker + GitHub Actions

## Como rodar localmente
```bash
pip install -r requirements.txt
python app.py
```

## Como rodar com Docker
```bash
docker build -t your-dockerhub-username/tasks-service .
docker run -p 5001:5000 your-dockerhub-username/tasks-service
```

## Testes
```bash
pytest -v
```

oi2