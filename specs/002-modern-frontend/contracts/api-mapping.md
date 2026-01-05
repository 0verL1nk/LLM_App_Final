# API Contract Mapping

## Authentication (`/api/v1/auth`)
- `POST /login`: Login with username/password
- `POST /register`: Create new account
- `POST /logout`: Invalidate token

## Files (`/api/v1/files`)
- `GET /`: List files (Paginated)
- `POST /upload`: Upload document (Multipart form)
- `GET /{id}`: Get file details
- `DELETE /{id}`: Delete file

## Documents (`/api/v1/documents`)
- `POST /{id}/summarize`: Generate summary (Body: options)
- `POST /{id}/qa`: Ask question (Body: question, history)
- `POST /{id}/rewrite`: Rewrite text (Body: text, style)
- `POST /{id}/mindmap`: Generate mindmap data

## Tasks (`/api/v1/tasks`)
- `GET /`: List user tasks
- `GET /{id}`: Get task status/result
- `POST /{id}/cancel`: Cancel task

## Users (`/api/v1/users`)
- `GET /me`: Get profile
- `PUT /api-key`: Update key
- `PUT /preferences`: Update UI settings
