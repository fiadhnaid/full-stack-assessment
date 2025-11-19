# Full-stack Developer Assessment

This project provides a Docker Compose setup for a full-stack application. It has a FastAPI backend and Next.js frontend that displays some information from the `Gapminder` dataset.

## Project Structure

```
.
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── src/
│          ├── __init____.py
│          ├── database.py
│          └── models.py
├── db/
│   ├── gapminder.csv
│   └── init.sql
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── tsconfig.json
    ├── next-env.d.ts
    ├── src/
        ├── pages/
        │   ├── index.tsx
        │   ├── _app.tsx
        │   └── api/
        │       └── gapminder.ts
        └── styles/
            ├── globals.css
            └── Home.module.css
```

## Features

- **Database**: Postgres server that loads in the gapminder dataset
- **Backend**: FastAPI serving a synthesized Gapminder dataset with country development metrics
- **Frontend**: Next.js with TypeScript that renders some of the dataset.
- **Development Environment**:
  - Hot reloading for both backend and frontend
  - Docker Compose setup for easy development

## Getting Started

1. Make sure you have Docker and Docker Compose installed on your system
2. Clone/download this repository
3. Navigate to the project directory
4. Run the following command to start the services:

```bash
docker-compose up --build
```
docker-compose logs -f backend

5. Access the applications:
   - FastAPI Backend: http://localhost:8000
   - Next.js Frontend: http://localhost:3000

## API Endpoints

- `GET /`: Returns a simple greeting message
- `GET /api/gapminder`: Returns the Gapminder dataset with life expectancy, GDP per capita, and population data

## Additional Commands

- To rebuild the containers:
  ```bash
  docker-compose up --build
  ```

- To stop the services:
  ```bash
  docker-compose down
  ```

## Development

Both frontend and backend directories are mounted as volumes, so any changes you make to the code will be reflected in the running application without needing to rebuild the containers. The setup includes hot reloading for both the FastAPI backend and Next.js frontend.

## Technologies Used

- **Backend**: FastAPI, Python
- **Frontend**: Next.js, TypeScript, Recharts
- **Database**: Postgres
- **Infrastructure**: Docker, Docker Compose