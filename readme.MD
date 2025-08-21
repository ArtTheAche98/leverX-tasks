### Local Setup (without Docker)

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install pip-tools:
   ```bash
   pip install pip-tools
   ```
3. Compile dependencies:
   ```bash
   pip-compile requirements.in
   ```
4. Install dependencies:
   ```bash
   pip-sync
   ```
5. Apply migrations:
   ```bash
   python manage.py migrate
   ```
6. Start the server:
   ```bash
   python manage.py runserver
   ```
7. Access API docs:  
   [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)

8. Or download the API documentation at:
   [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)
---

### Docker Setup

1. Build and start containers:
   ```bash
   docker compose up --build
   ```
2. Apply migrations (in another terminal):
   ```bash
   docker compose exec web python manage.py migrate
   ```
3. Access API docs:  
   [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)

---