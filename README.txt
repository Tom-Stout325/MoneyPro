W-9 public portal patch

What this patch changes:
- Adds a public portal base template with no MoneyPro navbar or internal navigation.
- Updates the W-9 portal page to use the public base.
- Updates the W-9 thank-you page to use the public base.
- Adds a small notice when the page is opened by a user who is already signed in to MoneyPro in that browser.

Files included:
- templates/public_portal_base.html
- contractor/templates/contractor/w9_portal.html
- contractor/templates/contractor/w9_thanks.html
