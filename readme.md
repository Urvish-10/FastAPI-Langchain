# ⚡ FastAPI + Langgraph + SQLModel Project

> ⚠️ **Note:** This Repository mainly focuses on the integration of Langgraph with FastAPI.

A modern asynchronous backend built with **FastAPI**, **SQLModel**, and **Uvicorn**, managed by the **uv** package manager, and running on **Python 3.13**.

This project provides a clean, modular structure with dedicated folders for API endpoints, models, utilities, and core logic. Database migrations (Alembic) are **not** used yet — schema management is manual.

---

## 🧱 Tech Stack

| Component | Description |
|------------|-------------|
| **Python** | 3.13 |
| **Package Manager** | [uv](https://github.com/astral-sh/uv) |
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) |
| **ORM / Models** | [SQLModel](https://sqlmodel.tiangolo.com/) |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) |
| **Database** | PostgreSQL |
| **Environment Variables** | `.env` file in project root |

---

## 📂 Project Structure

```
.
├── app/
│   ├── agent_utils/        # Agent-related utilities
│   ├── api/                # API routes / endpoints
│   ├── core/               # Core configurations and constants
│   ├── fixtures/           # Initial data, test fixtures, etc.
│   ├── models/             # SQLModel models and schemas
│   ├── utilities/          # Helper functions, tools
│   ├── __init__.py
│   └── main.py             # FastAPI entry point
│
├── .env                    # Environment variables
├── __init__.py             # Optional init script
├── pyproject.toml          # Project dependencies (managed by uv)
├── uv.lock                 # uv dependency lock file
├── readme.md               # Project documentation (this file)
├── result.csv              # Sample output/data file
└── test_main.http          # HTTP test file for API endpoints
```

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Urvish-10/FastAPI-Langchain.git
cd your-project
```

### 2. Install uv package manager

```bash
pip install uv
```

Verify the installation:

```bash
uv --version
```

### 3. Install project dependencies

```bash
uv sync
```

### 4. Configure environment variables

Create a `.env` file in the project root with the following variables, else refer the given `.env.example` file:

```env
SECRET_KEY="supersecret"

GOOGLE_API_KEY="your api key"

POSTGRES_SERVER="localhost"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="Test105*"
POSTGRES_DB="langgraph_sample"
```

### 5. Load the fixture data

```bash
python -m app.fixtures.user_data
```

### 6. Run the development server

```bash
uvicorn app.main:app --reload
```

### 7. Access the API documentation

Once the server is running, you can access:

- **Swagger UI** → http://127.0.0.1:8000/docs
- **ReDoc** → http://127.0.0.1:8000/redoc

---

## 🧰 Development Notes

- **No Alembic yet**: Database migrations are currently managed manually. Consider adding Alembic for automated schema migrations in production.

- **SQLModel**: Combines the best of SQLAlchemy and Pydantic, providing both ORM capabilities and data validation.

- **Core configuration**: Extend `app/core/` to include application configuration, logging setup, or constants.

- **API organization**: Group routes by feature or domain in `app/api/` for better maintainability.

- **Testing**: Use `test_main.http` for manual API testing, or add automated tests using pytest.

---

## 🚀 Future Enhancements

- [ ] Add Alembic for database migrations
- [ ] Implement comprehensive test suite with pytest
- [ ] Add authentication and authorization
- [ ] Set up CI/CD pipeline
- [ ] Add Docker support for containerization
- [ ] Implement logging and monitoring

---

## 📝 License

This project is licensed under the **MIT License**.  
See the [LICENSE](LICENSE) file for full details.

---


## 📧 Contact

**Urvish Bhatt**  
Software Engineer | Python • FastAPI • Django • DRF • AI • Agents • R&D Robotics

For questions, discussions, or collaboration opportunities, feel free to reach out:

- 📧 [urvishh.bhatt@gmail.com](mailto:urvishh.bhatt@gmail.com)  
- 🌐 [LinkedIn](https://www.linkedin.com/in/urvish-bhatt)

