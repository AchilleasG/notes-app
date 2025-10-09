# User Management

Since public registration is disabled, users must be created by administrators using the management command.

## Creating a New User

### Basic User Creation (Interactive)
```bash
# Run this in your Docker container or local environment
python manage.py create_user
```

This will prompt you for:
- Username
- Email address
- Password (entered securely)
- Password confirmation

### Command Line User Creation
```bash
# Create a regular user
python manage.py create_user --username johndoe --email john@example.com --bio "Software Developer" --location "New York"

# Create a superuser/admin
python manage.py create_user --username admin --email admin@example.com --superuser
```

### Docker Usage
```bash
# Interactive creation
sudo docker compose exec web python manage.py create_user

# Command line creation
sudo docker compose exec web python manage.py create_user --username newuser --email user@example.com
```

## Command Options

- `--username`: Username for the new user
- `--email`: Email address for the new user  
- `--password`: Password (if not provided, will prompt securely)
- `--superuser`: Create user as superuser/admin
- `--bio`: User bio/description
- `--location`: User location

## Examples

```bash
# Create admin user
python manage.py create_user --username admin --email admin@domain.com --superuser

# Create regular user with details
python manage.py create_user --username alice --email alice@domain.com --bio "Designer" --location "San Francisco"

# Interactive creation (recommended for secure password entry)
python manage.py create_user
```

## Security Notes

- Registration page has been removed from the public interface
- Only administrators can create new users via command line
- Passwords are validated for minimum length (8 characters)
- Email addresses are validated and must be unique
- Usernames must be unique
