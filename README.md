# Spam Detector Service

Stateless FastAPI service for detecting signals and extracting normalized entities from text.
Version **0.2.0** introduces a neutral detection contract. It does not decide whether a message
is spam or whether a chat policy passed.

## Responsibility boundary

Spam Detector:

- detects matches and entities;
- extracts links and phone numbers;
- normalizes and deduplicates results.

Sprotect:

- stores immutable chat configuration;
- applies `min_count`/`max_count` and other policies;
- decides whether policy passed and produces a moderation decision;
- performs Telegram actions.

For example, the same detection `phone count=1` can mean that Chat A's `min_count=1` policy
passed, Chat B's `max_count=0` policy failed, or Chat C has no phone policy and merely consumes
the detection. That interpretation never belongs in this service.

## API v2

`POST /api/v2/check` detects only the requested detector names. Unknown fields and duplicate
detectors are rejected with HTTP 422. `/api/check` remains available as deprecated v1 and keeps
its legacy behavior; new integrations must not use it.

Request:

```json
{
  "text": "sprotect_demo_token https://example.invalid/test +7 (000) 123-45-67",
  "detectors": ["blacklist", "links", "phone"],
  "options": {
    "blacklist": {"words": ["sprotect_demo_token"]},
    "links": {},
    "phone": {}
  }
}
```

Complete v2 request with all currently supported v2 detectors:

```json
{
  "text": "sprotect_demo_token https://example.invalid/test +7 (000) 123-45-67 @support_user user@example.org 😀",
  "detectors": [
    "blacklist", "links", "phone", "telegram_nick", "message_length",
    "email_addresses", "emoji_check", "async_exemple"
  ],
  "options": {
    "blacklist": {
      "words": ["sprotect_demo_token", "casino", "viagra"]
    },
    "links": {},
    "phone": {},
    "telegram_nick": {},
    "message_length": {"min_length": 10, "max_length": 2000},
    "email_addresses": {},
    "emoji_check": {"max_emoji": 10},
    "async_exemple": {"url": "https://detector.example/check", "timeout": 2.0}
  }
}
```

Only these request fields are accepted by v2. `links`, `phone`, `telegram_nick`, and
`email_addresses` accept empty option objects only; fields such as `max_links` are rejected.

Response:

```json
{
  "has_signals": true,
  "signal_count": 3,
  "results": [
    {
      "name": "blacklist",
      "detected": true,
      "confidence": 1.0,
      "count": 1,
      "details": {"hits": ["sprotect_demo_token"], "occurrences_count": 1}
    },
    {
      "name": "links",
      "detected": true,
      "confidence": 1.0,
      "count": 1,
      "details": {"links": ["https://example.invalid/test"]}
    },
    {
      "name": "phone",
      "detected": true,
      "confidence": 1.0,
      "count": 1,
      "details": {"phones": ["+70001234567"]}
    }
  ]
}
```

`detected` is exactly `count > 0`. `has_signals` only means that something was found; it does
not mean spam. Deterministic detectors report confidence `1.0` for both positive and negative
results because it describes confidence in the result, not severity.

### Detector contracts

- `blacklist`: requires 1–1000 words of at most 128 characters. Text and words use Unicode NFKC
  normalization and case folding, then substring matching. `hits` contains unique normalized
  words in request order; `count` is unique hits and `occurrences_count` counts all non-overlapping
  occurrences.
- `links`: accepts no options and extracts `http`/`https` URLs. Unique links retain first text
  appearance. It does not accept legacy `max_links`.
- `phone`: accepts no options. It recognizes RU/KZ (`+7`, `7`, or local `8`), Uzbekistan `+998`,
  and Belarus `+375` patterns with spaces, parentheses, and hyphens. Results use international
  digit format, retain first appearance, and are deduplicated. Extensions and unrelated short
  numbers are not recognized.
- `telegram_nick`: accepts no options and extracts `@` usernames that contain 5–32 ASCII letters,
  digits, or underscores.
- `message_length`: reports one signal when text length falls outside the configurable
  `min_length`/`max_length` range (10–2000 by default).
- `email_addresses`: accepts no options and extracts syntactically matching email addresses.
- `emoji_check`: extracts emoji code points from supported Unicode ranges; `max_emoji` is kept in
  result details for compatibility with v1 and does not filter v2 results.
- `async_exemple`: posts text to a configurable external service and treats its boolean `passed`
  response field as a signal. Network and response failures become signals only when
  `fail_on_error` is true.

Request limits are 20,000 text characters and eight detectors. More than 100 unique extracted
links or phones returns HTTP 422 with `detection_limit_exceeded`; results are never truncated.
Invalid request/options return HTTP 422. Unexpected detector failures return HTTP 500; partial
success is not returned.

See [the complete v2 detector reference](docs/00-static-checks.md) for request and response
examples.

## Deprecated API v1

`POST /api/check` is deprecated, but still supports all registered legacy checks. Its request
contract is intentionally permissive: `checks` contains check names and `options` is keyed by the
same names, with each value wrapped in `params`.

Complete legacy v1 request covering all currently registered checks:

```json
{
  "text": "free casino https://example.invalid/test +7 (000) 123-45-67 @support_user user@example.com 😀😀😀",
  "checks": [
    "blacklist",
    "links",
    "phone",
    "telegram_nick",
    "message_length",
    "email_addresses",
    "emoji_check",
    "async_exemple"
  ],
  "options": {
    "blacklist": {
      "params": {
        "words": ["free", "viagra", "casino"],
        "max_hits": 3
      }
    },
    "links": {
      "params": {
        "max_links": 3
      }
    },
    "phone": {
      "params": {}
    },
    "telegram_nick": {
      "params": {}
    },
    "message_length": {
      "params": {
        "min_length": 10,
        "max_length": 2000
      }
    },
    "email_addresses": {
      "params": {}
    },
    "emoji_check": {
      "params": {
        "max_emoji": 10
      }
    },
    "async_exemple": {
      "params": {
        "url": "https://example.com/api",
        "api_key": "",
        "timeout": 2.0,
        "fail_on_error": false,
        "payload": {}
      }
    }
  }
}
```

## Run and verify

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload
pytest
ruff check .
ruff format --check .
```

Swagger UI is at `http://localhost:8000/docs`; health is at `/health`.

Docker:

```bash
docker compose up --build
```

The v2 implementation does not log source text, options, extracted entities, or raw responses.
