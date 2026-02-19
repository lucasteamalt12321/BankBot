# Multiple Environment Support

The configuration system now supports multiple environments (development, test, staging, production) with environment-specific configuration files.

## How It Works

The Settings class automatically loads configuration from environment-specific `.env` files based on the `ENV` environment variable.

### Loading Priority

Configuration is loaded in the following priority order (highest to lowest):

1. **Environment variables** - Direct environment variables always take precedence
2. **Environment-specific .env file** - `config/.env.{ENV}` (e.g., `config/.env.production`)
3. **Default .env file** - `config/.env` (for backward compatibility)
4. **Default values** - Built-in defaults in the Settings class

### Supported Environments

- `development` (default)
- `test`
- `staging`
- `production`

## Usage

### Setting the Environment

Set the `ENV` environment variable to specify which environment to use:

```bash
# Linux/Mac
export ENV=production

# Windows PowerShell
$env:ENV="production"

# Windows CMD
set ENV=production
```

### Creating Environment-Specific Configuration Files

Create separate `.env` files for each environment in the `config/` directory:

```
config/
├── .env                    # Default/fallback configuration
├── .env.development        # Development environment
├── .env.test               # Test environment
├── .env.staging            # Staging environment
└── .env.production         # Production environment
```

### Example Configuration Files

#### config/.env.development
```env
ENV=development
BOT_TOKEN=your_development_bot_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot_dev.db
PARSING_ENABLED=false
LOG_LEVEL=DEBUG
LOG_FILE=logs/bot_dev.log
```

#### config/.env.production
```env
ENV=production
BOT_TOKEN=your_production_bot_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=postgresql://user:password@localhost:5432/bankbot_prod
PARSING_ENABLED=true
LOG_LEVEL=INFO
LOG_FILE=logs/bot_prod.log
```

### Using in Code

The configuration is automatically loaded when you import settings:

```python
from src.config import settings

# Access configuration values
print(f"Current environment: {settings.ENV}")
print(f"Bot token: {settings.BOT_TOKEN}")
print(f"Database URL: {settings.DATABASE_URL}")
```

### Environment-Specific Overrides

You can have common settings in `config/.env` and override specific values in environment files:

**config/.env** (common settings):
```env
ADMIN_TELEGRAM_ID=123456789
PARSING_ENABLED=false
LOG_LEVEL=INFO
```

**config/.env.production** (production overrides):
```env
ENV=production
BOT_TOKEN=prod_token_here
DATABASE_URL=postgresql://prod/db
PARSING_ENABLED=true
LOG_LEVEL=WARNING
```

When `ENV=production`, the system will:
1. Load common settings from `.env`
2. Override with production-specific settings from `.env.production`
3. Use environment variables if set

## Backward Compatibility

The system maintains full backward compatibility:

- If no `ENV` variable is set, defaults to `development`
- If no environment-specific file exists, falls back to `config/.env`
- Existing code using `from src.config import settings` continues to work without changes

## Running the Bot in Different Environments

### Development
```bash
# Uses config/.env.development
ENV=development python bot.py
```

### Production
```bash
# Uses config/.env.production
ENV=production python bot.py
```

### Testing
```bash
# Uses config/.env.test
ENV=test pytest
```

## Best Practices

1. **Never commit sensitive data** - Add `.env*` files to `.gitignore` (except `.env.example` files)
2. **Use example files** - Provide `.env.{environment}.example` files with dummy values
3. **Document required variables** - Keep `.env.example` files up to date
4. **Environment variables for secrets** - Use environment variables for sensitive data in production
5. **Validate on startup** - The Settings class validates all required fields on initialization

## Troubleshooting

### Missing Required Variables

If required variables are missing, you'll see a validation error:

```
ValidationError: 3 validation errors for Settings
BOT_TOKEN
  Field required [type=missing]
```

**Solution**: Ensure all required variables are set in your `.env` file or as environment variables.

### Wrong Environment

If the bot is using the wrong environment:

1. Check the `ENV` environment variable: `echo $ENV` (Linux/Mac) or `echo %ENV%` (Windows)
2. Verify the correct `.env.{ENV}` file exists in the `config/` directory
3. Check file permissions - ensure the `.env` files are readable

### Configuration Not Loading

If configuration changes aren't being picked up:

1. Restart the application (configuration is loaded once at startup)
2. Verify the `.env` file path is correct (`config/.env.{ENV}`)
3. Check for syntax errors in the `.env` file
4. Ensure environment variables don't have quotes around values

## Migration from Single .env File

If you're currently using a single `config/.env` file:

1. **No changes required** - The system will continue to work with your existing `.env` file
2. **Optional**: Create environment-specific files for better organization:
   ```bash
   cp config/.env config/.env.development
   cp config/.env config/.env.production
   # Edit each file with environment-specific values
   ```
3. **Set ENV variable** when running in different environments

## Example: Deploying to Production

1. Create `config/.env.production` with production values
2. Set environment variable: `export ENV=production`
3. Start the bot: `python bot.py`

The bot will automatically load production configuration from `config/.env.production`.
