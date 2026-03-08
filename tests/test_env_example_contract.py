from pathlib import Path


def test_env_example_contains_required_keys() -> None:
    env_example = Path(__file__).resolve().parents[1] / '.env.example'
    content = env_example.read_text()

    required = [
        'DATABASE_URL=',
        'TWILIO_AUTH_TOKEN=',
        'TWILIO_PHONE_NUMBER=',
        'FORM_TOKEN_SECRET=',
        'OPENAI_API_KEY=',
        'OPENAI_MODEL=',
        'TWILIO_VALIDATE_SIGNATURE=',
        'SMS_SEND_ENABLED=',
        'FORM_BASE_URL=',
        'CORS_ALLOW_ORIGINS=',
    ]

    for key in required:
        assert key in content, f'Missing {key} in .env.example'
