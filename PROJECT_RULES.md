# Project Operational Rules
**Last Updated:** January 27, 2026

Refer to these rules **before** performing any Notion or Slack automation actions.

## 1. 🛑 NOTION BOARD RESTRICTIONS (CRITICAL)
*   **Allowed Boards ONLY:** You may only access, create, or update tickets on boards found within the **Website Hosting & Project Management Hub**.
    *   **Hub URL:** [Website Hosting & Project Management Hub](https://www.notion.so/quickerleads/Website-Hosting-Project-Management-Hub-28e1c9f5b34f8088a7bff341be5aec2f)
*   **Old Boards:** Do NOT access or migrate tickets from old boards. They contain outdated data ("mad shit") and create confusion.
*   **Correction Protocol:** If a ticket is found on an old board:
    1.  **Do NOT Move It:** Moving tickets brings over legacy metadata issues.
    2.  **Manually Re-create:** Create a FRESH ticket on the correct board in the Hub.
    3.  **Delete Old:** Once the new ticket is confirmed, the old one can be deleted.

## 2. 📝 TICKET CONTENT RULES (NOTION ONLY)
*   **The Principle:** **"Comb Deeply, Write Concisely"**
    *   **Slack Inspection:** We must read and analyze ALL relevant Slack history to capture every detail. Do not skip context.
    *   **Notion Output:** The final ticket must be clean. summarize the findings.
*   **Minimal Notes:** Ticket descriptions in Notion must be concise summaries of the Slack findings.
*   **No "Wall of Text":** Do NOT paste raw 8,000-word Slack logs into the Notion ticket card.
*   **Long Content Strategy:** If the deep Slack dive unearths massive logs or long threads:
    *   Create a **Google Doc**.
    *   Paste the full raw context there.
    *   **Link the Google Doc** in the Notion ticket.
*   **Formatting:** Use bullet points and clear headers.

## 3. 🤖 AUTOMATION GUIDELINES
*   **Daily Sync:** When identifying tasks for the day, filter **strictly** by the Allowed Boards.
*   **Duplicates:** Aggressively identify and flag duplicates. Prefer the ticket on the official Hub board as the canonical one.

## 4. 🔑 API & ACCESS
*   **System State:** The `NOTION_API_KEY` and `SLACK_BOT_TOKEN` are currently missing/unset.
*   **Fallback Method:** Use **Browser Automation** (SlackBrowserClient) with the stored `browser_storage_state.json` to inspect Slack.
*   **Notion Access:** Notion browser access is currently failing (login required). Rely on Slack messages for task context until Notion session is refreshed.
