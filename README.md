# Gerenciador de Viagem

Aplicação web (Django full stack + PostgreSQL) para registrar e acompanhar os
gastos de uma viagem: abastecimentos (carro), hospedagem, alimentação e passeios
(ônibus), com dashboard, sincronização offline no mobile e relatório em PDF.

## Stack

- Python 3.12 + Django 6.0 (server-rendered, views CBV)
- PostgreSQL 18
- Poetry (`pyproject.toml` + `poetry.lock`) e Docker multi-stage (venv em `/venv`)
- ApexCharts (dashboard), matplotlib + wkhtmltopdf (relatório PDF)
- Sync offline no mobile: IndexedDB + endpoints JSON idempotentes (UUID)

## Desenvolvimento

```bash
cp .env.example .env             # opcional (defaults cobrem o dev)
docker compose up -d             # web em http://localhost:8003 + Postgres 18
docker compose exec web python manage.py createsuperuser --email voce@exemplo.com
docker compose exec web python manage.py test
```

- Usuários são criados pelo Django Admin (`/admin/`); login é por e-mail.
- O serviço `web` aplica as migrations pendentes automaticamente ao subir
  (só em dev; em produção o migrate continua manual — veja a seção abaixo).
- Sincronização: os lançamentos do mobile passam por `POST /sync/<recurso>/`
  (login + CSRF) e seguem para o servidor quando há conexão.

## Produção (Docker Swarm)

O banco **fica fora do ciclo de vida do stack** (RNF03): mantenha o PostgreSQL
18 em servidor/stack próprio, com volume persistente, e informe host/porta pelo
ambiente.

1. **Banco externo** (exemplo com um volume dedicado, fora do stack do app):

   ```bash
   docker volume create trip-manager-data
   docker run -d --name trip-manager-db --restart always \
     -e POSTGRES_DB=trip_manager -e POSTGRES_USER=trip_manager \
     -e POSTGRES_PASSWORD='<senha-forte>' \
     -v trip-manager-data:/var/lib/postgresql -p 5432:5432 postgres:18
   ```

2. **Build da imagem do app:**

   ```bash
   docker build -t project-trip-manager-web:latest .
   ```

3. **Variáveis de ambiente** (use um `.env` de produção e exporte):

   ```bash
   set -a; source .env; set +a
   ```

   Obrigatórias: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `POSTGRES_DB`,
   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `EMAIL_HOST`.
   Recomendadas: `DJANGO_CSRF_TRUSTED_ORIGINS` (ex.: `https://viagens.exemplo.com`),
   `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`,
   `DEFAULT_FROM_EMAIL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

   Segurança (default seguro, desligável): `DJANGO_SECURE_SSL_REDIRECT` (true),
   `DJANGO_SECURE_HSTS_SECONDS` (31536000). Em teste local sem TLS, defina
   `DJANGO_SECURE_SSL_REDIRECT=false`.

4. **Migrações (uma vez, antes do deploy):**

   ```bash
   docker run --rm --env-file .env project-trip-manager-web:latest \
     python manage.py migrate --settings=core.settings.prod
   ```

5. **Deploy do stack:**

   ```bash
   docker swarm init            # apenas na primeira vez no host
   docker stack deploy -c docker-stack.yml trip-manager
   docker stack services trip-manager
   ```

   O serviço roda `collectstatic` + `gunicorn` (3 workers) na porta 8003
   (ingress) e serve os estáticos via WhiteNoise.

6. **TLS**: termine HTTPS na frente (Traefik/nginx/caddy) e aponte para a porta
   8003; mantenha `DJANGO_CSRF_TRUSTED_ORIGINS` com o domínio público.

## Testes

```bash
docker compose exec web python manage.py test          # suíte completa no container
POSTGRES_HOST=localhost poetry run python manage.py test  # no host (sem wkhtmltopdf, com skips)
```

O projeto segue TDD: cada funcionalidade tem teste antes da implementação; o
histórico por fase fica em `.agents/context/historico/` e o contexto por app em
`.agents/context/`.
