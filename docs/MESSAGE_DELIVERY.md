# Message delivery

Reminders and messages are written by the system and queued. What happens next depends on the channel.

| Channel | How it is sent |
|---|---|
| Email | Automatically over SMTP once `SMTP_HOST` and `SMTP_FROM` are set. The scheduler sends queued email every 10 minutes; "Send email now" does it on demand. |
| WhatsApp, SMS | By a person, with the one-tap button, then "Mark sent". A WhatsApp/SMS provider (for example a WhatsApp Business API partner or an SMS bulk gateway) needs its own business account and is not connected yet. |

## Rules
- A member who opted out is never contacted; their queued message is cancelled.
- A failed email stays queued with the reason shown on screen, so it can still be sent by hand. After 3 failed tries (`DELIVERY_MAX_ATTEMPTS`) the scheduler stops retrying it.
- Each sent message records whether it went out automatically or was marked sent by a person.

## Setting up email
Use any SMTP service (your domain's mailbox, or a transactional service). Put the details in `backend/.env`, restart, and open Communications: the page tells you which channels are automatic.
