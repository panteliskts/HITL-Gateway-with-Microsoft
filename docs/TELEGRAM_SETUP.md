# Telegram Notifications Setup Guide

This guide will help you configure Telegram notifications for HITL Gateway escalations.

## Overview

When a HITL request is **manually escalated** or **SLA timeout is exceeded**, the system will automatically send a notification to your configured Telegram channel.

## Setup Steps

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a chat and send `/newbot`
3. Follow the prompts to create your bot:
   - Choose a name (e.g., "HITL Gateway Alerts")
   - Choose a username (e.g., "hitl_gateway_bot")
4. **Save the bot token** that BotFather provides (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)

### 2. Get Your Chat ID

#### Option A: Personal Chat
1. Send any message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"chat":{"id":123456789}` in the response
4. Save this number as your chat ID

#### Option B: Group/Channel
1. Add your bot to the group/channel
2. Send a message mentioning the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for `"chat":{"id":-100123456789}` (note: group IDs are negative)
5. Save this number as your chat ID

### 3. Configure Environment Variables

Create or update your `.env` file in the project root:

```bash
# Copy from .env.example if you haven't already
cp .env.example .env
```

Add your Telegram credentials to `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=123456789
```

### 4. Test the Integration

1. Start the backend server:
   ```bash
   cd backend
   python server.py
   ```

2. Trigger a demo scenario from the Live Demo page

3. Click the **Escalate** button when reviewing the request

4. You should receive a Telegram message like:
   ```
   🚨 HITL Gateway - ESCALATION ALERT

   Instance ID: abc-123-xyz
   Agent: secops-agent-v2
   Urgency: CRITICAL
   Action: Isolate host 10.0.5.42...

   Reviewer: jane.doe@contoso.com
   Reason: Escalated to senior review

   Time: 2026-03-28 10:30:45 UTC
   ━━━━━━━━━━━━━━━━━━━━
   Auto-escalated to senior review
   ```

## Notification Triggers

Telegram notifications are sent in these scenarios:

1. **Manual Escalation**: When a reviewer clicks "Escalate" instead of Approve/Reject
2. **SLA Timeout**: When no human decision is made within the SLA deadline:
   - CRITICAL: 5 minutes
   - HIGH: 15 minutes
   - NORMAL: 60 minutes
   - LOW: 24 hours

## Message Format

### Manual Escalation Message
```
🚨 HITL Gateway - ESCALATION ALERT

Instance ID: [workflow-id]
Agent: [agent-id]
Urgency: [urgency-level]
Action: [action-description]

Reviewer: [reviewer-email]
Reason: [escalation-reason]

Time: [timestamp]
━━━━━━━━━━━━━━━━━━━━
Auto-escalated to senior review
```

### SLA Timeout Message
```
⏱️ HITL Gateway - SLA TIMEOUT ESCALATION

Instance ID: [workflow-id]
Agent: [agent-id]
Urgency: [urgency-level]
Action: [action-description]

SLA Exceeded: [seconds]
Time: [timestamp]
━━━━━━━━━━━━━━━━━━━━
⚠️ No human decision received - Auto-escalated to senior review
```

## Troubleshooting

### Not receiving messages?

1. **Check bot token and chat ID**:
   ```bash
   # Test your bot token
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
   ```

2. **Check backend logs**:
   - Look for `[TELEGRAM]` log messages
   - If configured, you'll see: `Message sent successfully`
   - If not configured: `Skipping notification (not configured)`
   - Errors will show the specific issue

3. **Verify environment variables are loaded**:
   ```bash
   # In backend directory
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN'))"
   ```

4. **Check bot permissions**:
   - For groups: Ensure bot is an admin or can send messages
   - For channels: Bot must be added as an admin

### Common Issues

| Issue | Solution |
|-------|----------|
| "Unauthorized" | Check bot token is correct |
| "Chat not found" | Verify chat ID, send a message to bot first |
| "Bot was blocked" | Unblock the bot in Telegram |
| No logs appearing | Ensure `.env` file is in the correct location |

## Security Notes

⚠️ **NEVER commit your `.env` file to version control!**

- The `.gitignore` already excludes `.env` files
- Keep your bot token secret
- Rotate the token if compromised (via @BotFather)
- Use different bots for dev/staging/production

## Advanced Configuration

### Multiple Notification Channels

To send to multiple chats, you can modify `send_telegram_notification()` in `backend/server.py`:

```python
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_ID", "").split(",")

for chat_id in TELEGRAM_CHAT_IDS:
    payload = {"chat_id": chat_id.strip(), ...}
    # send message
```

Then in `.env`:
```bash
TELEGRAM_CHAT_ID=123456789,987654321,-100123456789
```

### Custom Message Formatting

Messages support HTML formatting:
- `<b>bold</b>` - **bold text**
- `<i>italic</i>` - *italic text*
- `<code>monospace</code>` - `monospace`
- `<a href="url">link</a>` - [hyperlink](url)

## Support

For issues with:
- **Telegram API**: Check [Telegram Bot API docs](https://core.telegram.org/bots/api)
- **HITL Gateway**: Check the main README or raise an issue

---

**Status**: ✅ Implemented in backend v2.1.0+
