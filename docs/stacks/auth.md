# Auth Stacks

## AuthStack
- Cognito **User Pool**
  - Self-signup by email
  - (Optional) Google/Facebook/GitHub providers
- **Resource Server**: identifier `myapi-<stage>`
  - Scope: `usage.read`
- **App Clients**
  - **WebAppClient**: authorization-code grant; scopes `openid email profile`
  - **BackendClient**: client-credentials grant; scopes `myapi-<stage>/usage.read`

## AuthApiStack
- Attaches a Cognito authorizer to API methods (`/v1/...`)
- Identity source: `Authorization` header (`Bearer <token>`)

## Token flows

**Client-credentials (M2M)**

curl -X POST https://<domain>/oauth2/token
-u "<BACKEND_CLIENT_ID>:<BACKEND_CLIENT_SECRET>"
-H "Content-Type: application/x-www-form-urlencoded"
-d "grant_type=client_credentials&scope=myapi-<stage>/usage.read"


**Auth-code (optional)**
- Hosted UI domain → `/login?response_type=code&client_id=...&redirect_uri=...`
- Exchange `code` at `/oauth2/token`


