# Security UI Integration Guide

## Overview

The security features are now integrated into the user interface across three main areas:

1. **Login Page** - Shows password policy requirements and rate limiting information
2. **Change Password Form** - Real-time password policy validation with user feedback
3. **User Management (Admin)** - Password policy enforcement during user creation and password reset

## Features

### 1. Login Page (`templates/login.html`)

**What Users See:**
- Password policy requirements displayed upfront (minimum 10 characters, no leading/trailing spaces)
- Expandable security details section showing:
  - Rate limiting policy (5 failures = 10-minute lockout)
  - Cross-origin protection status
  - Session security details
- Demo account credentials clearly marked

**User Flow:**
1. User reads password policy upfront
2. On failed login, flash message indicates lockout status if applicable
3. Expandable menu provides detailed security context without cluttering the form

---

### 2. Change Password Form (`templates/change_password.html`)

**What Users See:**
- Clear policy statement above password input (minimum 10 characters)
- **Real-time validation feedback** below the password field:
  - Shows "⚠ Too short (7/10 chars)" while typing
  - Shows "Remove leading/trailing spaces" if whitespace issues detected
  - Shows "✓ Password meets policy requirements" when valid

**User Flow:**
1. User sees policy requirements
2. As they type, feedback updates in real-time
3. JavaScript disables submit button until password is valid
4. User gets immediate confirmation before submitting

**Technical Details:**
- `minlength="10"` HTML attribute for browser-level validation
- Client-side JavaScript validates with same rules as server
- Submit button disabled until all requirements met
- Server-side validation ensures security even if JavaScript disabled

---

### 3. User Management Admin Page (`templates/users.html`)

**What Admins See:**

#### Create User Section
- Info box explaining password policy to all new users
- Password field requires 10+ characters with real-time feedback
- Matching feedback display as users type
- Submit button disabled until password is valid

#### Reset Password Section
- Inline password reset form in "Reset Pwd" collapsible
- Same 10+ character requirement with live validation
- Helpful text: "Must be 10+ characters, no leading/trailing spaces"

**Admin Workflow:**
1. Admin sees policy requirements before creating users
2. When typing new user password, gets real-time validation feedback
3. Same protection during password reset operations
4. Consistent experience across all password-entry scenarios

---

## Real-Time Validation Logic

All password fields use the same client-side validation logic (in `static/security_ui.js`):

```javascript
SecurityUI.validatePassword(passwordValue) {
    // Returns: { valid: true/false, message: "...", errors: [...] }
    // Checks:
    // 1. Length >= 10 characters
    // 2. No leading/trailing whitespace
}
```

**Visual Feedback:**
- `⚠` Red (#c74945) = Does not meet requirements
- `✓` Green (#2f7757) = Meets all requirements
- Blank = User hasn't typed yet

---

## Security Information Component

A reusable component is provided: `templates/components/security_info_panel.html`

**To include on any admin page:**
```html
{% include 'components/security_info_panel.html' %}
```

Displays:
- Password policy (10+ chars, no leading/trailing spaces, no reuse)
- Login protection (5 failures, 15-min window, 10-min lockout)
- Session security (HttpOnly, Secure, SameSite cookies)
- Request validation (same-origin, security headers)
- Environment variable override information

---

## CSS Styling

Custom CSS classes added to `static/style.css`:

```css
[data-policy-feedback]          /* Highlight password policy inputs */
[data-admin-pwd]                /* Admin password field styling */
[minlength="10"]:focus          /* Focus state styling */

#password-feedback              /* Real-time feedback container */
#admin-password-feedback        /* Admin form feedback */
.password-policy-feedback       /* Generic feedback class */

details > summary               /* Expandable security sections */
details[open] > summary         /* Open state styling */
```

---

## JavaScript Utilities

Optional helper script available: `static/security_ui.js`

**Available Functions:**

```javascript
// Display policy in target element
SecurityUI.displayPasswordPolicy(elementId)

// Display rate limit info
SecurityUI.displayRateLimitInfo(elementId)

// Validate password (returns object with valid, message, and errors)
SecurityUI.validatePassword(passwordValue)

// Setup real-time validation on an input
SecurityUI.setupPasswordValidation(inputId, feedbackId)

// Setup bulk validation on multiple fields
SecurityUI.setupBulkPasswordValidation(selectors)

// Show info modal
SecurityUI.showSecurityInfo(title, content)

// Get security config from meta tags
SecurityUI.getSecurityConfig()
```

---

## Server-Side Enforcement

All client-side validation is **also enforced on the server:**

- [`/login` route](app.py#L2271): Rate limit checked before auth attempt
- [`/change-password` route](app.py#L2315): Password validation before update
- [`/admin/users` route (POST)](app.py#L3678): Validation on user creation
- [`/admin/users/<id>/reset-password` route](app.py#L3772): Validation on admin reset

**Important:** Client-side UI is for UX only. Server always validates.

---

## Flash Messages

Security-related feedback is shown via Flask flash messages:

```python
# Rate limit exceeded (shown on login page)
flash("Too many sign-in attempts. Try again in 10 minutes.", "danger")

# Password policy violation (shown on change-password page)
flash("New password must be at least 10 characters and cannot have leading/trailing spaces.", "danger")

# Admin operations (shown on user management page)
flash("Password policy requires minimum 10 characters.", "danger")
```

Categories map to Bootstrap alert classes:
- `"danger"` → `<div class="alert alert-danger">`
- `"warning"` → `<div class="alert alert-warning">`
- `"success"` → `<div class="alert alert-success">`
- `"info"` → `<div class="alert alert-info">`

---

## Testing the UI

### Manual Testing

1. **Login Page**
   - Visit `/login` (or navigate when not authenticated)
   - Read password policy info box
   - Click "Security & Rate Limiting" to expand details
   - Attempt login with wrong credentials 5+ times to trigger lockout message

2. **Change Password**
   - Log in with demo account (admin/admin123)
   - Visit `/change-password`
   - Type password < 10 chars → See feedback
   - Type password with leading space → See feedback
   - Type valid 10+ char password → See ✓ confirmation

3. **Admin User Creation**
   - Log in as admin
   - Go to `/admin/users`
   - Scroll to "Create User" section
   - Try entering password < 10 chars → See feedback
   - Submit valid password → User created

### Automated Testing

Test coverage in `tests/test_auth_security.py`:

```bash
pytest tests/test_auth_security.py -v
```

Current tests:
- `test_login_page_loads()` - Verifies page renders with policy info
- `test_dashboard_redirects_when_not_authenticated()` - Auth flow
- `test_cross_origin_post_is_blocked()` - CSRF protection
- `test_login_rate_limit_blocks_after_repeated_failures()` - Rate limiting

---

## Browser Compatibility

- **Modern Browsers** (Chrome, Firefox, Safari, Edge): Full support
  - Real-time validation with JavaScript
  - HTML5 `minlength` attribute
  - CSS transitions and animations
  - Details/summary expandable sections

- **JavaScript Disabled**: Still works
  - HTML5 `minlength` provides fallback validation
  - Server-side validation always enforces policy
  - Less user-friendly but still secure

---

## Customization

### Changing Password Policy

Edit [app.py lines 123-126](app.py#L123-L126):

```python
MIN_PASSWORD_LENGTH = int(os.getenv('TIMETABLE_MIN_PASSWORD_LENGTH', 10))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('TIMETABLE_LOGIN_WINDOW_SECONDS', 900))
LOGIN_RATE_LIMIT_MAX_FAILURES = int(os.getenv('TIMETABLE_LOGIN_MAX_FAILURES', 5))
LOGIN_RATE_LIMIT_LOCK_SECONDS = int(os.getenv('TIMETABLE_LOGIN_LOCK_SECONDS', 600))
```

### Changing UI Colors

Edit `static/style.css`:

```css
:root {
    --brand-500: #8f2750;      /* Primary brand color */
    --danger-500: #c74945;     /* Error/warning color */
    --success-500: #2f7757;    /* Success color */
}
```

### Custom Security Info

Edit `templates/components/security_info_panel.html` to add/remove policy sections.

---

## Summary

The security features are now fully integrated into the user interface with:

✅ **Upfront policy communication** on all password-entry forms
✅ **Real-time validation feedback** with visual indicators
✅ **Consistent user experience** across login, change password, and admin workflows
✅ **Server-side enforcement** ensuring security regardless of client behavior
✅ **Accessibility** with clear error messages and keyboard navigation
✅ **Graceful degradation** when JavaScript is disabled

Users understand security requirements before attempting actions, and get immediate feedback when requirements aren't met.
