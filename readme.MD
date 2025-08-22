### Local Setup for the final project (CourseManagement) ; (without Docker)

1. Clone the repository and enter the project directory

```bash
git clone git@github.com:ArtTheAche98/leverX-tasks.git
cd CourseManagement
```

2.Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3.Install pip-tools:
   ```bash
   pip install pip-tools
   ```
4.Compile dependencies:
   ```bash
   pip-compile requirements.in
   ```
5.Install dependencies:
   ```bash
   pip-sync
   ```
6. Install libmagic (required for file type detection):

   - **macOS:**  
     ```bash
     brew install libmagic
     ```
   - **Ubuntu/Debian:**  
     ```bash
     sudo apt-get install libmagic1
     ```
   - **Windows:**  
     ```bash
     choco install libmagic
     ```
     Or download and install from [GnuWin32](http://gnuwin32.sourceforge.net/packages/file.htm)

7.Apply migrations:
   ```bash
   python manage.py migrate
   ```
8.Start the server:
   ```bash
   python manage.py runserver
   ```
9.Access API docs:  
   [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)

10.Or download the API documentation at:
   [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

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