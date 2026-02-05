# Auth Flows

## Client-credentials (recommended to start)
**Token**
```bash
curl -X POST https://<domain>/oauth2/token \
  -u "<BACKEND_CLIENT_ID>:<BACKEND_CLIENT_SECRET>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&scope=myapi-<stage>/usage.read"


Call API

curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/v1/usage/log \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"svc","token_count":5,"endpoint":"/v1/usage/log"}'

Authorization-code (optional)

- Hosted UI: /login?response_type=code&client_id=...&redirect_uri=https://httpbin.org/get
- Exchange code:

curl -X POST https://<domain>/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&client_id=<WEBAPPCLIENT_ID>&code=<CODE>&redirect_uri=https:/