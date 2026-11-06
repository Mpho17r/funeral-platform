# Forgot password and email verification

## For people
- **Forgot password?** on the sign-in page asks for your email address. If an account uses it, a link arrives that works for 60 minutes and only once. Choosing a new password signs you out everywhere else, lifts any lock from too many wrong tries, and emails you a notice that it changed.
- **Confirm your email.** New owners, and staff an administrator adds, get a confirmation link (valid 3 days). Until it is used a yellow bar offers to send it again. Nothing is blocked while unconfirmed. Resetting a password through the emailed link also confirms the address. People who already had an account are treated as confirmed.
- An administrator can still set a new password for someone (Settings > Team) if their email is out of reach.

## How it is kept safe
- The form gives the same answer whether or not the address has an account, so it cannot be used to find out who is a customer.
- Tokens are random; only a hash is stored. Each works once, expires, and asking again cancels the earlier link. A confirmation link only counts for the address it was sent to.
- At most 3 reset emails and 5 confirmation emails per account per hour.
- Links carry the token after `#` (`/reset-password#token=...`), so it never reaches server logs or other sites.
- Resets and confirmations are written to the audit trail (never the password or token).

## What the server needs
| Setting | Why |
|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Without them no email goes out. On a developer machine the link is printed in the backend log instead; on a live system it is not. |
| `PUBLIC_APP_URL` | Address used in the emailed links, for example `https://app.yourbusiness.co.za`. On a live system it defaults to your first `CORS_ORIGINS` address. |

Update steps: `python3 -m alembic upgrade head` (one new migration), then restart the backend.

## Not included
No rate limit by internet address yet (only per account); put the server behind a proxy that limits `/auth/*` when it is public. Confirmation is not enforced, because a server without email could never confirm anyone.
