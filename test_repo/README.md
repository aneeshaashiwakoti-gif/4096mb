# Test Repo

This is a small synthetic repository used to validate the ingestion/chunking pipeline.

## Files

| File      | Language   | Purpose                          |
|-----------|------------|----------------------------------|
| auth.py   | Python     | Auth tokens, password hashing    |
| db.js     | JavaScript | Connection pool, query helpers   |
| api.ts    | TypeScript | Router class, request handlers   |

## Usage

Run the smoke test against this folder:

```bash
python main.py --repo test_repo --single-file test_repo/auth.py
```
