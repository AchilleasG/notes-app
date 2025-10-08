# Docker Setup Instructions

This project includes a complete Docker setup for running the Django application with Pydantic-based configuration management.

## Quick Start

1. **Copy the environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the .env file** with your database configuration.

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

The application will be available at `http://localhost:8001`

## Configuration Management

This project uses **Pydantic Settings** for robust environment variable management with:
- ✅ Type validation
- ✅ Automatic .env file loading
- ✅ Default values
- ✅ Field validation
- ✅ Better error messages

## Environment Variables

Edit the `.env` file to configure your application:

### Django Settings
- `DEBUG`: Set to `True` for development, `False` for production (boolean)
- `SECRET_KEY`: Django secret key (generate a new one for production)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### PostgreSQL Database Configuration
- `DB_NAME`: Database name (required)
- `DB_USER`: Database username (required)
- `DB_PASSWORD`: Database password (required)
- `DB_HOST`: Database host (required)
- `DB_PORT`: Database port (defaults to 5432)

## Database Configuration

The application is configured to use PostgreSQL with Pydantic validation. You need to provide the connection details for your existing PostgreSQL database in the `.env` file:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=your_host
DB_PORT=5432
```

## Benefits of Pydantic Settings

- **Type Safety**: Automatic conversion and validation of environment variables
- **Default Values**: Sensible defaults when environment variables aren't set
- **Validation**: Rich validation with helpful error messages
- **Documentation**: Self-documenting configuration with field descriptions
- **IDE Support**: Better autocomplete and type hints

## Docker Commands

- **Build and start:** `docker-compose up --build`
- **Start in background:** `docker-compose up -d`
- **Stop:** `docker-compose down`
- **View logs:** `docker-compose logs`
- **Execute commands in container:** `docker-compose exec web python manage.py <command>`

## Development

The Docker setup includes volume mounting for development, so changes to your code will be reflected immediately without rebuilding the container.

For running Django management commands:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py collectstatic
```
