# Privacy and security rules (binding for all contributors, human or AI)

This project can observe a person. It must stay a tool the **owner controls**.

1. **Owner consent and control.** The PC owner enables each remote capability separately:
   study stats, domains, messages, snapshot, live view. Default for everything remote is OFF.
2. **Visible indicator.** Whenever the camera or screen is accessed, the PC shows an obvious
   on-screen indicator and logs it (who, what, when). Never hidden. Never silent.
3. **Approval for camera/screen.** Camera and screen access require either live owner approval
   or an owner-set schedule/permission that the owner can revoke instantly (kill switch).
4. **Least data.** Share minutes, streak, and domains by default. No page contents, no
   keystrokes, no passwords, no screenshots unless explicitly requested and approved.
5. **Strong auth.** The viewer account uses login with 2FA. No shared passwords in code.
6. **Local-first network.** The local API binds to 127.0.0.1. Remote access goes through
   Tailscale or an authenticated cloud API, never an open port on the router.
7. **Secrets.** Keys live in `.env` / `config.toml` (git-ignored). Never commit secrets.
8. **Mutual by design.** The viewer can share her own goals/data too, but only data she
   explicitly chooses; nothing is pulled from her phone silently.
9. **Escape hatch.** Lock mode must always have a delayed emergency override, so the owner is
   never locked out of the PC for real work or emergencies.
10. **No dual use.** Do not add stealth features, hidden persistence, or anything that would
    work against the person being monitored.
